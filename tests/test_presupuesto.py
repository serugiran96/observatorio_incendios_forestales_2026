"""Matriz de presupuesto: no se inventan costos y los escenarios solo usan supuestos explícitos."""

import math

import pandas as pd
import pytest

from observatorio import config, presupuesto
from observatorio import evidencias as registro


@pytest.fixture(scope="module")
def costos():
    return presupuesto.cargar_costos()


def test_catalogo_de_costos_valido(costos):
    assert presupuesto.validar_costos(costos, registro.cargar_fuentes()) == []


def test_costo_sin_fuente_es_error(costos):
    alterado = costos.copy()
    alterado.loc[0, "costo_unitario_soles"] = 150.0
    alterado.loc[0, "estado_costo"] = "referencial"
    errores = presupuesto.validar_costos(alterado, registro.cargar_fuentes())
    assert any("sin fuente_costo" in e for e in errores)


def test_costo_pendiente_no_puede_tener_valor(costos):
    alterado = costos.copy()
    alterado.loc[0, "costo_unitario_soles"] = 150.0
    alterado.loc[0, "fuente_costo"] = "F-0001"
    errores = presupuesto.validar_costos(alterado, registro.cargar_fuentes())
    assert any("pendiente de cotización" in e for e in errores)


def test_linea_sin_costo_no_calcula_total(costos):
    fila = costos.set_index("id_intervencion", drop=False).loc["H01"].astype(object)
    linea = presupuesto._linea(fila, {"provincia": "Canas"}, "Damnificados", "6 personas", 6.0, "EDAN", [], [])
    assert math.isnan(linea["costo_total_soles"]) and linea["brecha"] == presupuesto.SIN_COSTO


def test_linea_con_costo_y_sin_recursos_calcula_brecha(costos):
    fila = costos.set_index("id_intervencion", drop=False).loc["H01"].astype(object)
    fila["costo_unitario_soles"] = 100.0  # valor de prueba, no es un costo real
    linea = presupuesto._linea(fila, {"provincia": "Canas"}, "Damnificados", "6 personas", 6.0, "EDAN", [], [])
    assert linea["costo_total_soles"] == 600.0 and linea["brecha_soles"] == 600.0
    con_recursos = presupuesto._linea(fila, {}, "", "", 6.0, "EDAN", ["entrega documentada"], [])
    assert math.isnan(con_recursos["brecha_soles"])


def test_escenario_multiplica_y_excluye_lineas_sin_cantidad():
    matriz = pd.DataFrame({
        "id_linea": ["L-1", "L-2", "L-3"], "componente": ["humanitaria"] * 3,
        "id_intervencion": ["H01", "H01", "H01"], "intervencion": ["BAH"] * 3, "cantidad": [4.0, 6.0, None],
    })
    resultado = presupuesto.escenario(matriz, {"H01": 10.0}).iloc[0]
    assert resultado["total_escenario_soles"] == 100.0
    assert resultado["lineas_sin_cantidad"] == 1


RUTA = config.DIR_PROCESSED / "matriz_presupuesto.csv"


@pytest.mark.skipif(not RUTA.exists(), reason="ejecute scripts/construir_matrices.py")
def test_matriz_procesada_no_tiene_costos_inventados():
    matriz = pd.read_csv(RUTA)
    sin_fuente = matriz["fuente_costo"].fillna("").eq("")
    assert matriz.loc[sin_fuente, "costo_total_soles"].isna().all()
    assert matriz.loc[sin_fuente, "estado_costo"].eq("pendiente de cotización").all()
    assert matriz["id_linea"].is_unique
