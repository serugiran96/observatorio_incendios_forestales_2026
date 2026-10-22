"""Descarga los focos de calor de NASA FIRMS (VIIRS y MODIS) para Cusco y los cruza con el inventario.

Requiere FIRMS_MAP_KEY en .env (clave gratuita: https://firms.modaps.eosdis.nasa.gov/api/map_key/).

Uso:
    uv run python scripts/descargar_focos_calor.py [--inicio 2026-08-01] [--fin 2026-10-21]

Salidas:
    data/raw/geodatos/firms_crudo_<fuente>.csv          respuestas originales de la API (no versionado)
    data/processed/focos_calor_cusco.csv                focos dentro de Cusco con distrito asignado
    data/processed/focos_calor_distrito_dia.csv         conteo de focos por distrito y día
    data/processed/corroboracion_satelital.csv          focos en el distrito ±días de cada incendio del inventario
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd
import requests

from observatorio import config, focos_calor, territorio


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 8, 1))
    parser.add_argument("--fin", type=date.fromisoformat, default=config.FECHA_CORTE)
    args = parser.parse_args()

    clave = config.leer_variable_entorno("FIRMS_MAP_KEY")
    if not clave:
        print("Falta FIRMS_MAP_KEY en .env. Solicite una clave gratuita en "
              "https://firms.modaps.eosdis.nasa.gov/api/map_key/ y vuelva a ejecutar.")
        return 1
    estado = requests.get(focos_calor.URL_ESTADO_CLAVE.format(clave=clave), timeout=60)
    print(f"Estado de la clave FIRMS: {estado.text[:200]}")

    distritos = territorio.cargar_distritos()
    caja = tuple(distritos.total_bounds)  # oeste, sur, este, norte
    partes = []
    for fuente in focos_calor.FUENTES:
        crudo = focos_calor.descargar(clave, fuente, caja, args.inicio, args.fin)
        crudo.to_csv(config.DIR_GEODATOS / f"firms_crudo_{fuente}.csv", index=False)
        print(f"{fuente}: {len(crudo)} focos en la caja de Cusco")
        partes.append(focos_calor.normalizar(crudo))

    focos = focos_calor.asignar_distritos(pd.concat(partes, ignore_index=True), distritos)
    focos.drop(columns="geometry").sort_values("fecha_hora_local").to_csv(
        config.DIR_PROCESSED / "focos_calor_cusco.csv", index=False, encoding="utf-8"
    )
    por_dia = focos.groupby(["ubigeo", "provincia", "distrito", "fecha_local", "sensor"]).size().rename("focos").reset_index()
    por_dia.to_csv(config.DIR_PROCESSED / "focos_calor_distrito_dia.csv", index=False, encoding="utf-8")

    inventario = pd.read_csv(config.DIR_PROCESSED / "incendios_cusco_georreferenciado.csv", dtype={"ubigeo": str})
    corroboracion = focos_calor.corroborar(inventario, focos)
    corroboracion.to_csv(config.DIR_PROCESSED / "corroboracion_satelital.csv", index=False, encoding="utf-8")

    con_focos = (corroboracion["focos_en_ventana"] > 0).sum()
    print(f"Focos dentro de Cusco: {len(focos)} | incendios del inventario con focos en el distrito y fecha: "
          f"{con_focos}/{len(corroboracion)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
