"""Ejecuta el análisis satelital de la temporada de incendios 2026 en Cusco con Google Earth Engine.

Requiere:
    - GEE_PROJECT en .env y haber ejecutado `uv run earthengine authenticate`.
    - data/processed/limites_cusco_distritos.geojson (scripts/descargar_limites.py).
    - Opcional: data/processed/focos_calor_cusco.csv (scripts/descargar_focos_calor.py). Si no existe,
      se usan los focos MODIS del catálogo FIRMS de Earth Engine (1 km, menos sensibles).

Uso:
    uv run python scripts/ejecutar_analisis_gee.py

Salidas (data/processed/):
    gee_estadisticas_distrito.csv     ha de quemado probable por severidad, cobertura y pendiente; cambio no atribuido;
                                      área quemada MODIS MCD64A1 como referencia
    gee_metadatos.json                periodos, número de imágenes, parámetros y fecha de ejecución
    mapas/dnbr_cusco.png              dNBR para superponer en el mapa (con sus límites geográficos)
    mapas/quemado_probable_cusco.png  máscara de área quemada probable
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

import pandas as pd
import requests

from observatorio import config, gee_analisis as ga, territorio

DIR_MAPAS = config.DIR_PROCESSED / "mapas"


def main() -> int:
    ee = ga.inicializar(config.leer_variable_entorno("GEE_PROJECT"))
    distritos = territorio.cargar_distritos()
    distritos_fc = ga.coleccion_desde_geodataframe(ee, distritos, ["ubigeo", "provincia", "distrito"])
    region = distritos_fc.geometry().dissolve(maxError=100)
    periodos = ga.PERIODOS_TEMPORADA_2026

    focos_fc, origen_focos = None, "FIRMS MODIS (catálogo de Earth Engine)"
    ruta_focos = config.DIR_PROCESSED / "focos_calor_cusco.csv"
    if ruta_focos.exists():
        focos = pd.read_csv(ruta_focos, parse_dates=["fecha_local"])
        focos = focos[(focos["fecha_local"] >= pd.Timestamp(periodos.pre_fin)) & (focos["sensor"] == "VIIRS")]
        puntos = [ee.Feature(ee.Geometry.Point([f.longitud, f.latitud])) for f in focos.itertuples()]
        focos_fc, origen_focos = ee.FeatureCollection(puntos), f"FIRMS VIIRS descargado ({len(puntos)} focos)"

    pre, post, n_pre, n_post = ga.compuestos(ee, region, periodos)
    valida, cobertura = ga.mascara_valida(ee)
    cerca = ga.mascara_cerca_de_focos(ee, region, periodos, focos_fc)
    resultado = ga.severidad_y_quemado(ee, pre, post, valida, cerca)

    # Estadísticas por distrito
    stats = ga.estadisticas_por_distrito(ee, resultado, cobertura, distritos_fc)
    modis = ga.area_quemada_modis(ee, distritos_fc, periodos.pre_fin, periodos.post_fin)
    tabla = pd.DataFrame([f["properties"] for f in stats.getInfo()["features"]])
    tabla_modis = pd.DataFrame([f["properties"] for f in modis.getInfo()["features"]])[["ubigeo", "ha_modis_mcd64a1"]]
    tabla = tabla.merge(tabla_modis, on="ubigeo", how="left")
    renombres = {f"ha_sev_{k}": f"ha_sev_{c[2]}" for k, c in enumerate(ga.CLASES_SEVERIDAD)}
    renombres |= {f"ha_cob_{k}": f"ha_cob_{v}" for k, v in ga.COBERTURAS.items()}
    tabla = tabla.rename(columns=renombres).round(2)
    tabla.to_csv(config.DIR_PROCESSED / "gee_estadisticas_distrito.csv", index=False, encoding="utf-8")

    # Imágenes para el mapa del dashboard (sin credenciales en tiempo de ejecución)
    DIR_MAPAS.mkdir(parents=True, exist_ok=True)
    oeste, sur, este, norte = distritos.total_bounds
    caja = ee.Geometry.Rectangle([oeste, sur, este, norte])
    vistas = {
        "dnbr_cusco.png": resultado.select("dNBR").visualize(
            min=-0.1, max=0.66, palette=["1a9850", "ffffbf", "fdae61", "f46d43", "a50026"]),
        "quemado_probable_cusco.png": resultado.select("quemado_probable").selfMask().visualize(palette=["d7301f"]),
    }
    for nombre, imagen in vistas.items():
        url = imagen.clip(region).getThumbURL({"region": caja, "dimensions": 2048, "format": "png"})
        (DIR_MAPAS / nombre).write_bytes(requests.get(url, timeout=300).content)

    metadatos = {
        "ejecutado": datetime.now().isoformat(timespec="seconds"),
        "periodos": {k: v.isoformat() for k, v in periodos.__dict__.items()},
        "imagenes_sentinel2": {"pre": n_pre.getInfo(), "post": n_post.getInfo()},
        "umbral_cloud_score": ga.UMBRAL_CLOUD_SCORE,
        "umbral_dnbr_quemado": ga.UMBRAL_QUEMADO,
        "radio_focos_m": ga.RADIO_FOCOS_M,
        "unidad_minima_pixeles": ga.UNIDAD_MINIMA_PIXELES,
        "origen_focos": origen_focos,
        "limites_imagenes": {"oeste": oeste, "sur": sur, "este": este, "norte": norte},
    }
    (config.DIR_PROCESSED / "gee_metadatos.json").write_text(json.dumps(metadatos, indent=2, ensure_ascii=False))
    print(f"Quemado probable: {tabla['ha_quemado_probable'].sum():,.0f} ha | "
          f"cambio no atribuido: {tabla['ha_cambio_no_atribuido'].sum():,.0f} ha | "
          f"MODIS MCD64A1: {tabla['ha_modis_mcd64a1'].sum():,.0f} ha")
    return 0


if __name__ == "__main__":
    sys.exit(main())
