"""Consistencia de los archivos procesados versionados (inventario e indicadores distritales)."""

import pandas as pd
import pytest

from observatorio import config, territorio

RUTA_INVENTARIO = config.DIR_PROCESSED / "incendios_cusco_georreferenciado.csv"
RUTA_INDICADORES = config.DIR_PROCESSED / "indicadores_distrito.csv"

pytestmark = pytest.mark.skipif(not RUTA_INDICADORES.exists(), reason="ejecute scripts/agregar_por_distrito.py")


def test_todo_incendio_tiene_ubigeo_oficial():
    inventario = pd.read_csv(RUTA_INVENTARIO, dtype={"ubigeo": str})
    oficiales = set(territorio.cargar_distritos()["ubigeo"])
    for codigos in inventario["ubigeo"]:
        assert set(codigos.split("|")) <= oficiales


def test_indicadores_cubren_los_112_distritos_y_cuadran_con_el_inventario():
    indicadores = pd.read_csv(RUTA_INDICADORES, dtype={"ubigeo": str})
    inventario = pd.read_csv(RUTA_INVENTARIO, dtype={"ubigeo": str})
    assert len(indicadores) == 112
    fechas = pd.to_datetime(inventario["fecha_ocurrencia"])
    inicio, fin = (pd.Timestamp(f) for f in config.PERIODO_PRIORITARIO)
    periodo = inventario[(fechas >= inicio) & (fechas <= fin)]
    # Cada incendio cuenta una vez por cada distrito que abarca
    assert indicadores["n_incendios"].sum() == periodo["ubigeo"].str.split("|").str.len().sum()


def test_cifras_no_negativas():
    indicadores = pd.read_csv(RUTA_INDICADORES)
    numericas = indicadores.select_dtypes("number")
    assert (numericas.fillna(0) >= 0).all().all()
