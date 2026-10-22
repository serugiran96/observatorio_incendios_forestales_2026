"""Descarga los límites distritales de la región Cusco con código UBIGEO y población.

Fuente: servicio de cartografía de OSINERGMIN, capa "Límites distritales del Perú" (UBIGEO INEI,
nombres oficiales y población 2018). Se consulta solo el departamento de Cusco (código 08).

Uso:
    uv run python scripts/descargar_limites.py

Salidas:
    data/raw/geodatos/limites_cusco_distritos_completo.geojson   resolución original (no versionado)
    data/processed/limites_cusco_distritos.geojson               simplificado (~100 m) para mapas
    data/processed/limites_cusco_provincias.geojson              provincias (unión de distritos)
"""

from __future__ import annotations

import sys

import geopandas as gpd
import requests

from observatorio import config

URL_SERVICIO = (
    "https://gisem.osinergmin.gob.pe/serverosih/rest/services/Cartografia/LIMITES_DISTRITALES/MapServer/0/query"
)
TOLERANCIA_GRADOS = 0.001  # ~100 m; suficiente para mapas del dashboard


def descargar_distritos() -> gpd.GeoDataFrame:
    parametros = {
        "where": f"CODDEPARTAMENTO='{config.CODIGO_DEPARTAMENTO_CUSCO}'",
        "outFields": "UBIGEO,NOMDISTRITO,NOMPROVINCIA,POBLACION",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "geojson",
    }
    respuesta = requests.get(URL_SERVICIO, params=parametros, timeout=300)
    respuesta.raise_for_status()
    distritos = gpd.read_file(respuesta.text)
    distritos = distritos.rename(
        columns={"UBIGEO": "ubigeo", "NOMDISTRITO": "distrito", "NOMPROVINCIA": "provincia", "POBLACION": "poblacion_2018"}
    )
    distritos = distritos.set_crs(config.CRS_GEOGRAFICO, allow_override=True)
    distritos["area_km2"] = (distritos.to_crs(config.CRS_AREA).area / 1e6).round(2)
    return distritos[["ubigeo", "provincia", "distrito", "poblacion_2018", "area_km2", "geometry"]].sort_values("ubigeo")


def main() -> int:
    distritos = descargar_distritos()
    config.DIR_GEODATOS.mkdir(parents=True, exist_ok=True)
    distritos.to_file(config.DIR_GEODATOS / "limites_cusco_distritos_completo.geojson", driver="GeoJSON")

    simplificados = distritos.copy()
    simplificados["geometry"] = simplificados.geometry.simplify(TOLERANCIA_GRADOS, preserve_topology=True)
    simplificados.to_file(config.DIR_PROCESSED / "limites_cusco_distritos.geojson", driver="GeoJSON")

    provincias = simplificados.dissolve(by="provincia", as_index=False, aggfunc={"poblacion_2018": "sum", "area_km2": "sum"})
    provincias[["provincia", "poblacion_2018", "area_km2", "geometry"]].to_file(
        config.DIR_PROCESSED / "limites_cusco_provincias.geojson", driver="GeoJSON"
    )
    print(
        f"Distritos: {len(distritos)} | provincias: {provincias['provincia'].nunique()} | "
        f"área: {distritos['area_km2'].sum():,.0f} km² | población 2018: {distritos['poblacion_2018'].sum():,}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
