"""Descarga el Mapa Nacional de Ecosistemas del Perú (MINAM, 2018) para la región Cusco y calcula la
composición de ecosistemas de cada distrito.

El archivo nacional pesa más de 1 GB; aquí se consulta el servicio de mapas del MINAM solo para el
rectángulo de Cusco, por páginas, con geometría generalizada (~50 m), y luego se recorta al límite
regional.

Uso:
    uv run python scripts/descargar_ecosistemas.py

Salidas:
    data/raw/geodatos/ecosistemas_cusco_bruto.geojson       polígonos descargados (no versionado)
    data/processed/ecosistemas_cusco.geojson                ecosistemas recortados y disueltos por tipo (simplificado)
    data/processed/ecosistemas_por_distrito.csv             hectáreas de cada ecosistema por distrito
"""

from __future__ import annotations

import json
import sys
import time

import geopandas as gpd
import pandas as pd
import requests

from observatorio import config, territorio

URL = (
    "https://geoservidorperu.minam.gob.pe/arcgis/rest/services/Servicios_GeoPERU/"
    "ServicioEcosistemas_MINAM/MapServer/0/query"
)
TAMANO_PAGINA = 1000
GENERALIZACION_GRADOS = 0.0005  # ~50 m
SIMPLIFICACION_MAPA = 0.004  # ~400 m, solo para la capa del dashboard


def _parametros(envolvente: dict) -> dict:
    return {
        "geometry": json.dumps({**envolvente, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "1=1",
    }


def descargar(envolvente: dict) -> gpd.GeoDataFrame:
    """Descarga todos los polígonos por páginas. El servicio puede devolver menos registros que el
    tamaño de página (geometrías nulas), así que se avanza por desplazamiento hasta el total informado."""
    conteo = requests.post(URL, data={**_parametros(envolvente), "returnCountOnly": "true", "f": "json"}, timeout=120)
    conteo.raise_for_status()
    total = conteo.json()["count"]
    partes = []
    for desplazamiento in range(0, total, TAMANO_PAGINA):
        parametros = {
            **_parametros(envolvente),
            "outSR": "4326",
            "outFields": "OBJECTID,eco_detall,eco_layer",
            "maxAllowableOffset": GENERALIZACION_GRADOS,
            "geometryPrecision": 5,
            "orderByFields": "OBJECTID",
            "resultOffset": desplazamiento,
            "resultRecordCount": TAMANO_PAGINA,
            "f": "geojson",
        }
        respuesta = requests.post(URL, data=parametros, timeout=300)
        respuesta.raise_for_status()
        pagina = gpd.read_file(respuesta.text)
        partes.append(pagina)
        print(f"  {min(desplazamiento + TAMANO_PAGINA, total)}/{total} consultados ({len(pagina)} recibidos)")
        time.sleep(0.5)
    datos = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True), crs=config.CRS_GEOGRAFICO)
    return datos.drop_duplicates("OBJECTID")


def main() -> int:
    distritos = territorio.cargar_distritos()
    xmin, ymin, xmax, ymax = distritos.total_bounds
    bruto_ruta = config.DIR_GEODATOS / "ecosistemas_cusco_bruto.geojson"
    if bruto_ruta.exists():
        bruto = gpd.read_file(bruto_ruta)
    else:
        bruto = descargar({"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax})
        bruto.to_file(bruto_ruta, driver="GeoJSON")

    bruto = bruto.rename(columns={"eco_detall": "ecosistema"})
    bruto["geometry"] = bruto.geometry.make_valid()
    # Intersección con distritos en proyección de igual área para medir hectáreas
    ecos = gpd.overlay(
        bruto[["ecosistema", "geometry"]].to_crs(config.CRS_AREA),
        distritos[["ubigeo", "provincia", "distrito", "geometry"]].to_crs(config.CRS_AREA),
        how="intersection",
        keep_geom_type=True,
    )
    ecos["ha"] = ecos.area / 1e4
    tabla = ecos.groupby(["ubigeo", "provincia", "distrito", "ecosistema"], as_index=False)["ha"].sum()
    tabla["pct_distrito"] = (tabla["ha"] / tabla.groupby("ubigeo")["ha"].transform("sum") * 100).round(2)
    tabla["ha"] = tabla["ha"].round(1)
    tabla.sort_values(["ubigeo", "ha"], ascending=[True, False]).to_csv(
        config.DIR_PROCESSED / "ecosistemas_por_distrito.csv", index=False, encoding="utf-8"
    )

    mapa = ecos.dissolve(by="ecosistema", as_index=False)[["ecosistema", "geometry"]].to_crs(config.CRS_GEOGRAFICO)
    mapa["geometry"] = mapa.geometry.simplify(SIMPLIFICACION_MAPA, preserve_topology=True)
    mapa = mapa[~mapa.geometry.is_empty]
    mapa.to_file(config.DIR_PROCESSED / "ecosistemas_cusco.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

    resumen = tabla.groupby("ecosistema")["ha"].sum().sort_values(ascending=False)
    area_region = distritos.to_crs(config.CRS_AREA).area.sum() / 1e4
    print(f"Ecosistemas en Cusco: {len(resumen)} | superficie: {resumen.sum():,.0f} ha "
          f"({resumen.sum() / area_region:.1%} del área regional)")
    print(resumen.head(15).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
