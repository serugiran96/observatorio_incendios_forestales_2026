"""Reglas de agregación compartidas por scripts y dashboard (duplicados e incendios de varios distritos).

Los registros sintéticos son ficticios y solo ejercitan las reglas.
"""

import pandas as pd
import pytest

from observatorio import config, indicadores


def _inventario():
    return pd.DataFrame({
        "id_evento": ["A", "B", "C", "D"],
        "ubigeo": ["080701", "080701", "080701|080702", "080702"],
        "varios_distritos": ["False", "False", "True", "False"],
        "posibles_duplicados": ["B", "A", None, None],
        "cobertura_natural_destruida_ha": ["10", "25", "40", "5"],
        **{c: [None] * 4 for c in indicadores.CIFRAS if c != "cobertura_natural_destruida_ha"},
    })


def test_de_cada_grupo_de_duplicados_se_conserva_el_de_mayor_cobertura():
    assert indicadores.excluir_duplicados(_inventario()) == {"A"}


def test_incendio_de_varios_distritos_cuenta_en_cada_uno_sin_repartir_cifras():
    agregado = indicadores.agregar_por_ubigeo(_inventario()).set_index("ubigeo")
    assert agregado.loc["080701", "n_incendios"] == 3
    assert agregado.loc["080702", "n_incendios"] == 2
    # 080701: solo B (A es duplicado; C es de varios distritos y no se reparte)
    assert agregado.loc["080701", "cobertura_natural_destruida_ha"] == 25
    assert agregado.loc["080702", "cobertura_natural_destruida_ha"] == 5


def test_suma_sin_duplicados():
    assert indicadores.sumar_sin_duplicados(_inventario())["cobertura_natural_destruida_ha"] == 30


RUTA_INVENTARIO = config.DIR_PROCESSED / "incendios_cusco_georreferenciado.csv"
RUTA_INDICADORES = config.DIR_PROCESSED / "indicadores_distrito.csv"


@pytest.mark.skipif(not RUTA_INDICADORES.exists(), reason="ejecute scripts/agregar_por_distrito.py")
def test_dashboard_y_script_dan_las_mismas_cifras():
    inventario = pd.read_csv(RUTA_INVENTARIO, dtype={"ubigeo": str})
    fechas = pd.to_datetime(inventario["fecha_ocurrencia"])
    inicio, fin = (pd.Timestamp(f) for f in config.PERIODO_PRIORITARIO)
    agregado = indicadores.agregar_por_ubigeo(inventario[(fechas >= inicio) & (fechas <= fin)]).set_index("ubigeo")
    script = pd.read_csv(RUTA_INDICADORES, dtype={"ubigeo": str}).set_index("ubigeo")
    script = script[script["n_incendios"] > 0]
    assert (agregado.loc[script.index, "n_incendios"] == script["n_incendios"]).all()
    diferencia = agregado.loc[script.index, "cobertura_natural_destruida_ha"] - script["cobertura_destruida_ha_sin_duplicados"]
    assert diferencia.abs().max() < 1e-6
