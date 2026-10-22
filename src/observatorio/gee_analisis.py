"""Análisis satelital con Google Earth Engine: índices espectrales, severidad de quemado estimada,
área quemada probable y estadísticas por distrito.

Criterios metodológicos (ver docs/metodologia.md):
- Sentinel-2 SR armonizado (10–20 m) con máscara de nubes Cloud Score+ (cs >= 0,60).
- NBR = (B8 − B12)/(B8 + B12); NDVI = (B8 − B4)/(B8 + B4); dNBR = NBR_pre − NBR_post.
- Severidad por dNBR con los umbrales de Key y Benson (2006, USGS). Están calibrados para bosques de
  Norteamérica y sin validación de campo (CBI) en Cusco; se presentan como "severidad estimada".
- Un cambio solo se considera "área quemada probable" si coincide en espacio y tiempo con focos de
  calor; el resto de pérdidas de vegetación se informa como "cambio no atribuido" (cosechas,
  sequía, nubes residuales, etc. también reducen el NBR).
- Se excluyen agua, zonas urbanas y nieve/hielo (ESA WorldCover 2021, JRC Global Surface Water).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

# --- Colecciones -----------------------------------------------------------------
S2 = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_SCORE = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
WORLDCOVER = "ESA/WorldCover/v200"
DEM = "COPERNICUS/DEM/GLO30"
AGUA = "JRC/GSW1_4/GlobalSurfaceWater"
MCD64A1 = "MODIS/061/MCD64A1"
FIRMS_GEE = "FIRMS"  # MODIS, 1 km; se usa si no hay focos VIIRS descargados

UMBRAL_CLOUD_SCORE = 0.60
ESCALA_M = 20  # resolución de B12 en Sentinel-2
UNIDAD_MINIMA_PIXELES = 5  # 5 píxeles de 20 m = 0,2 ha; elimina ruido aislado
RADIO_FOCOS_M = 1500  # distancia máxima a un foco de calor para atribuir el cambio a fuego
PENDIENTE_EROSION_GRADOS = 30.0

# --- Severidad (Key y Benson, 2006) -------------------------------------------------
# (límite inferior, límite superior, clase); dNBR en escala de reflectancia (no ×1000)
CLASES_SEVERIDAD = [
    (-math.inf, -0.10, "regeneración"),
    (-0.10, 0.10, "sin cambio"),
    (0.10, 0.27, "baja"),
    (0.27, 0.44, "moderada-baja"),
    (0.44, 0.66, "moderada-alta"),
    (0.66, math.inf, "alta"),
]
UMBRAL_QUEMADO = 0.10  # dNBR mínimo para considerar posible quemado

# Clases de ESA WorldCover v200
COBERTURAS = {
    10: "árboles",
    20: "matorral",
    30: "pastizal/pajonal",
    40: "cultivo",
    50: "urbano",
    60: "suelo desnudo/vegetación escasa",
    70: "nieve/hielo",
    80: "agua",
    90: "humedal herbáceo (bofedal)",
    95: "manglar",
    100: "musgos/líquenes",
}
COBERTURAS_EXCLUIDAS = (50, 70, 80)


@dataclass(frozen=True)
class Periodos:
    """Ventanas de los compuestos antes y después de la temporada de incendios."""

    pre_inicio: date
    pre_fin: date
    post_inicio: date
    post_fin: date


PERIODOS_TEMPORADA_2026 = Periodos(date(2026, 7, 1), date(2026, 8, 15), date(2026, 10, 1), date(2026, 10, 21))


# --- Funciones puras (verificables sin Earth Engine) --------------------------------
def nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    return (nir - swir2) / (nir + swir2)


def ndvi(nir: np.ndarray, rojo: np.ndarray) -> np.ndarray:
    return (nir - rojo) / (nir + rojo)


def clasificar_dnbr(valor: float) -> str:
    for inferior, superior, clase in CLASES_SEVERIDAD:
        if inferior <= valor < superior:
            return clase
    return "sin dato"


# --- Earth Engine -----------------------------------------------------------------
def inicializar(proyecto: str | None):
    """Inicializa Earth Engine con el proyecto de Google Cloud indicado (GEE_PROJECT en .env)."""
    import ee

    if not proyecto:
        raise RuntimeError(
            "Falta GEE_PROJECT. Copie .env.example a .env y escriba el ID de su proyecto de Google Cloud "
            "con la API de Earth Engine habilitada."
        )
    try:
        ee.Initialize(project=proyecto)
    except Exception as error:  # ee lanza distintas excepciones según el problema de credenciales
        raise RuntimeError(
            "No se pudo inicializar Earth Engine. Ejecute en una terminal: "
            "`uv run earthengine authenticate` y vuelva a intentarlo. Detalle: " + str(error)
        ) from error
    return ee


def coleccion_desde_geodataframe(ee, gdf, columnas: list[str]):
    """Convierte un GeoDataFrame (EPSG:4326) en ee.FeatureCollection."""
    return ee.FeatureCollection(gdf[columnas + ["geometry"]].__geo_interface__)


def _s2_enmascarado(ee, region, inicio: date, fin: date):
    nubes = ee.ImageCollection(CLOUD_SCORE)

    def preparar(imagen):
        valida = imagen.select("cs").gte(UMBRAL_CLOUD_SCORE)
        refl = imagen.select(["B4", "B8", "B12"]).divide(10000)
        indices = refl.addBands([
            refl.normalizedDifference(["B8", "B4"]).rename("NDVI"),
            refl.normalizedDifference(["B8", "B12"]).rename("NBR"),
        ])
        return indices.updateMask(valida).copyProperties(imagen, ["system:time_start"])

    return (
        ee.ImageCollection(S2)
        .filterBounds(region)
        .filterDate(inicio.isoformat(), fin.isoformat())
        .linkCollection(nubes, ["cs"])
        .map(preparar)
    )


def compuestos(ee, region, periodos: Periodos):
    """Medianas pre y post (NDVI, NBR) y número de imágenes usadas en cada una."""
    pre = _s2_enmascarado(ee, region, periodos.pre_inicio, periodos.pre_fin)
    post = _s2_enmascarado(ee, region, periodos.post_inicio, periodos.post_fin)
    return pre.median(), post.median(), pre.size(), post.size()


def mascara_valida(ee):
    """Píxeles analizables: sin agua permanente, zona urbana ni nieve/hielo."""
    cobertura = ee.ImageCollection(WORLDCOVER).first().select("Map")
    excluir = cobertura.remap(list(COBERTURAS_EXCLUIDAS), [1] * len(COBERTURAS_EXCLUIDAS), 0)
    agua = ee.Image(AGUA).select("occurrence").unmask(0).gt(50)
    return excluir.Not().And(agua.Not()), cobertura


def mascara_cerca_de_focos(ee, region, periodos: Periodos, focos_fc=None):
    """1 donde hay focos de calor a menos de RADIO_FOCOS_M durante el periodo entre compuestos.

    `focos_fc`: FeatureCollection de puntos VIIRS (si se descargaron de FIRMS); si es None se usan
    los focos MODIS del catálogo FIRMS de Earth Engine.
    """
    inicio, fin = periodos.pre_fin.isoformat(), periodos.post_fin.isoformat()
    if focos_fc is not None:
        # Zonas circulares alrededor de cada foco; se rasterizan a la escala de la consulta
        zonas = focos_fc.filterBounds(region).map(lambda foco: foco.buffer(RADIO_FOCOS_M))
        return ee.Image(0).byte().paint(zonas, 1)
    firms = ee.ImageCollection(FIRMS_GEE).filterDate(inicio, fin).select("T21")
    focos = firms.max().setDefaultProjection(firms.first().projection()).gt(0).unmask(0)
    return focos.focalMax(RADIO_FOCOS_M, "circle", "meters")


def severidad_y_quemado(ee, pre, post, valida, cerca_focos):
    """Devuelve una imagen con bandas dNBR, dNDVI, clase de severidad, quemado probable y cambio no atribuido."""
    dnbr = pre.select("NBR").subtract(post.select("NBR")).rename("dNBR")
    dndvi = pre.select("NDVI").subtract(post.select("NDVI")).rename("dNDVI")
    cambio = dnbr.gte(UMBRAL_QUEMADO).And(valida)
    # Unidad mínima: elimina grupos de menos de UNIDAD_MINIMA_PIXELES píxeles conectados
    conectados = cambio.selfMask().connectedPixelCount(100, True).gte(UNIDAD_MINIMA_PIXELES).unmask(0)
    cambio = cambio.And(conectados)
    quemado = cambio.And(cerca_focos).rename("quemado_probable")
    no_atribuido = cambio.And(cerca_focos.Not()).rename("cambio_no_atribuido")
    limites = [c[1] for c in CLASES_SEVERIDAD[:-1]]  # -0.10, 0.10, 0.27, 0.44, 0.66
    clase = ee.Image(0)
    for k, limite in enumerate(limites, start=1):
        clase = clase.where(dnbr.gte(limite), k)
    return ee.Image.cat([dnbr, dndvi, clase.rename("clase_severidad").toByte(), quemado, no_atribuido])


def estadisticas_por_distrito(ee, resultado, cobertura, distritos_fc):
    """Hectáreas de quemado probable por severidad, cobertura y pendiente, por distrito."""
    ha = ee.Image.pixelArea().divide(1e4)
    quemado = resultado.select("quemado_probable")
    pendiente = ee.Terrain.slope(
        ee.ImageCollection(DEM).select("DEM").mosaic().setDefaultProjection("EPSG:4326", None, 30)
    )
    bandas = [
        ha.updateMask(quemado).rename("ha_quemado_probable"),
        ha.updateMask(resultado.select("cambio_no_atribuido")).rename("ha_cambio_no_atribuido"),
        ha.updateMask(quemado.And(pendiente.gte(PENDIENTE_EROSION_GRADOS))).rename("ha_quemado_pendiente_30"),
    ]
    for k, (_, _, nombre) in enumerate(CLASES_SEVERIDAD):
        if nombre in ("regeneración", "sin cambio"):
            continue
        bandas.append(ha.updateMask(quemado.And(resultado.select("clase_severidad").eq(k))).rename(f"ha_sev_{k}"))
    for codigo in COBERTURAS:
        if codigo in COBERTURAS_EXCLUIDAS:
            continue
        bandas.append(ha.updateMask(quemado.And(cobertura.eq(codigo))).rename(f"ha_cob_{codigo}"))
    imagen = ee.Image.cat(bandas).unmask(0)
    return imagen.reduceRegions(collection=distritos_fc, reducer=ee.Reducer.sum(), scale=ESCALA_M, tileScale=8)


def area_quemada_modis(ee, distritos_fc, inicio: date, fin: date):
    """Área quemada MODIS MCD64A1 (500 m) por distrito, como referencia independiente y gruesa."""
    quemado = (
        ee.ImageCollection(MCD64A1).filterDate(inicio.isoformat(), fin.isoformat()).select("BurnDate").max().gt(0)
    )
    ha = ee.Image.pixelArea().divide(1e4).updateMask(quemado).rename("ha_modis_mcd64a1").unmask(0)
    return ha.reduceRegions(collection=distritos_fc, reducer=ee.Reducer.sum(), scale=500)
