"""Focos de calor (anomalías térmicas activas) de NASA FIRMS: descarga, limpieza y cruce con el
inventario de incendios.

Un foco de calor es un píxel (375 m VIIRS, 1 km MODIS) con una anomalía térmica en el momento del
paso del satélite. NO equivale a hectáreas quemadas: un incendio puede generar muchos focos, ninguno
(nubes, incendio breve entre pasos) o focos que no son incendios forestales (quemas agrícolas,
industrias). Aquí se usan solo como indicio independiente de que hubo fuego en un lugar y fecha.

API: https://firms.modaps.eosdis.nasa.gov/api/area/ (requiere MAP_KEY gratuita).
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import geopandas as gpd
import pandas as pd
import requests

from observatorio import config

URL_AREA = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{clave}/{fuente}/{area}/{dias}/{fecha}"
URL_ESTADO_CLAVE = "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={clave}"
# Fuentes en tiempo casi real (NRT). Para fechas antiguas existen versiones "_SP" (procesamiento estándar).
FUENTES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT")
MAX_DIAS_POR_CONSULTA = 10
DESFASE_PERU_HORAS = -5  # FIRMS entrega la hora en UTC

_CONFIANZA_VIIRS = {"l": "baja", "n": "nominal", "h": "alta"}


def ventanas(inicio: date, fin: date, dias: int = MAX_DIAS_POR_CONSULTA) -> list[tuple[date, int]]:
    """Divide [inicio, fin] en ventanas (fecha_inicial, n_dias) aceptadas por la API."""
    resultado, actual = [], inicio
    while actual <= fin:
        n = min(dias, (fin - actual).days + 1)
        resultado.append((actual, n))
        actual += timedelta(days=n)
    return resultado


def descargar(clave: str, fuente: str, caja: tuple[float, float, float, float], inicio: date, fin: date) -> pd.DataFrame:
    """Descarga los focos de una fuente para la caja (oeste, sur, este, norte) y el periodo dado."""
    area = ",".join(f"{v:.4f}" for v in caja)
    partes = []
    for fecha, dias in ventanas(inicio, fin):
        url = URL_AREA.format(clave=clave, fuente=fuente, area=area, dias=dias, fecha=fecha.isoformat())
        respuesta = requests.get(url, timeout=120)
        respuesta.raise_for_status()
        if respuesta.text.strip().lower().startswith(("invalid", "error")):
            raise RuntimeError(f"FIRMS rechazó la consulta ({fuente}, {fecha}): {respuesta.text[:200]}")
        tabla = pd.read_csv(io.StringIO(respuesta.text))
        if not tabla.empty:
            tabla["fuente_firms"] = fuente
            partes.append(tabla)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def normalizar(crudo: pd.DataFrame) -> pd.DataFrame:
    """Unifica columnas de VIIRS y MODIS: fecha/hora local, confianza en tres niveles, FRP."""
    if crudo.empty:
        return pd.DataFrame(columns=["fecha_hora_local", "fecha_local", "latitud", "longitud", "sensor", "satelite",
                                     "confianza", "frp_mw", "dia_noche", "fuente_firms"])
    hora = crudo["acq_time"].astype(int).astype(str).str.zfill(4)
    utc = pd.to_datetime(crudo["acq_date"] + " " + hora, format="%Y-%m-%d %H%M")
    local = utc + pd.Timedelta(hours=DESFASE_PERU_HORAS)

    def confianza(valor) -> str:
        texto = str(valor).strip().lower()
        if texto in _CONFIANZA_VIIRS:
            return _CONFIANZA_VIIRS[texto]
        numero = float(texto)  # MODIS: 0–100
        return "baja" if numero < 30 else "alta" if numero >= 80 else "nominal"

    return pd.DataFrame({
        "fecha_hora_local": local,
        "fecha_local": local.dt.date,
        "latitud": crudo["latitude"].astype(float),
        "longitud": crudo["longitude"].astype(float),
        "sensor": crudo["instrument"].astype(str),
        "satelite": crudo["satellite"].astype(str),
        "confianza": crudo["confidence"].map(confianza),
        "frp_mw": crudo["frp"].astype(float),
        "dia_noche": crudo["daynight"].map({"D": "día", "N": "noche"}),
        "fuente_firms": crudo["fuente_firms"],
    })


def asignar_distritos(focos: pd.DataFrame, distritos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Une cada foco con el distrito que lo contiene; descarta los que caen fuera de Cusco."""
    puntos = gpd.GeoDataFrame(
        focos, geometry=gpd.points_from_xy(focos["longitud"], focos["latitud"]), crs=config.CRS_GEOGRAFICO
    )
    unidos = gpd.sjoin(puntos, distritos[["ubigeo", "provincia", "distrito", "geometry"]], how="inner", predicate="within")
    return unidos.drop(columns="index_right")


def corroborar(inventario: pd.DataFrame, focos: pd.DataFrame, dias_antes: int = 1, dias_despues: int = 3) -> pd.DataFrame:
    """Cuenta los focos del mismo distrito entre `dias_antes` y `dias_despues` de la fecha de cada incendio.

    `inventario` necesita las columnas id_evento, ubigeo (puede listar varios con "|") y fecha_ocurrencia.
    El resultado indica coincidencia espacio-temporal, no prueba que los focos sean de ese incendio.
    """
    focos = focos.assign(fecha_local=pd.to_datetime(focos["fecha_local"]))
    filas = []
    for evento in inventario.itertuples(index=False):
        fecha = pd.Timestamp(evento.fecha_ocurrencia)
        ubigeos = str(evento.ubigeo).split("|") if isinstance(evento.ubigeo, str) and evento.ubigeo else []
        cercanos = focos[
            focos["ubigeo"].isin(ubigeos)
            & (focos["fecha_local"] >= fecha - pd.Timedelta(days=dias_antes))
            & (focos["fecha_local"] <= fecha + pd.Timedelta(days=dias_despues))
        ]
        filas.append({
            "id_evento": evento.id_evento,
            "focos_en_ventana": len(cercanos),
            "focos_confianza_alta": int((cercanos["confianza"] == "alta").sum()),
            "frp_max_mw": cercanos["frp_mw"].max() if len(cercanos) else None,
            "corroboracion_satelital": "con focos de calor en el distrito y fecha" if len(cercanos) else "sin focos detectados",
        })
    return pd.DataFrame(filas)
