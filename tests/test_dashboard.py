"""Prueba de humo del dashboard: cada página se ejecuta sin errores con los datos procesados."""

from datetime import date

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from observatorio import config, tablero

APP = str(config.RAIZ_PROYECTO / "app.py")
PAGINAS = ["paginas/resumen.py", "paginas/mapa.py", "paginas/ficha.py", "paginas/atencion.py",
           "paginas/restauracion.py", "paginas/presupuesto.py", "paginas/metodologia.py"]

requiere_datos = pytest.mark.skipif(
    not (config.DIR_PROCESSED / "matriz_presupuesto.csv").exists(), reason="ejecute scripts/construir_matrices.py")


@requiere_datos
@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_sin_errores(pagina):
    app = AppTest.from_file(APP, default_timeout=180)
    app.run()
    if pagina != PAGINAS[0]:
        app.switch_page(pagina)
        app.run()
    assert not app.exception, [e.value for e in app.exception]


@requiere_datos
def test_filtro_por_provincia_reduce_el_resumen():
    app = AppTest.from_file(APP, default_timeout=180)
    app.run()
    total = app.metric[0].value
    app.sidebar.multiselect[0].set_value(["Chumbivilcas"]).run()
    assert not app.exception
    assert int(app.metric[0].value) < int(total)


def test_formato_numerico_en_espanol():
    assert tablero.fmt(8328.3, 1) == "8 328,3"
    assert tablero.fmt(None) == "—"


def test_aplicar_filtros_admite_varios_distritos():
    datos = pd.DataFrame({"fecha_ocurrencia": ["2026-09-10", "2026-10-01", "2026-08-01"],
                          "provincia": ["Anta", "Anta", "Anta"], "ubigeo": ["080301", "080302|080303", "080303"],
                          "estado": ["abierto al último reporte"] * 3})
    filtros = tablero.Filtros(date(2026, 9, 1), date(2026, 10, 21), ["Anta"], ["080303"], [])
    assert list(tablero.aplicar(datos, filtros)["ubigeo"]) == ["080302|080303"]
