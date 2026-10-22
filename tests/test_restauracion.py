"""Catálogo de medidas de restauración y su aplicación por distrito."""

import pandas as pd
import pytest

from observatorio import config, restauracion
from observatorio import evidencias as registro


@pytest.fixture(scope="module")
def medidas():
    return restauracion.cargar_medidas()


def _distrito(**cambios):
    base = {"ubigeo": "080701", "provincia": "Chumbivilcas", "distrito": "Santo Tomas", "area_km2": 1000.0,
            "n_incendios": 3, "cobertura_destruida_ha_sin_duplicados": 50.0, "ha_pajonal": 0.0, "ha_bofedal": 0.0,
            "ha_bosque": 0.0, "ha_zona_agricola": 0.0, "cultivos_ha": 0.0, "ganado_perdido": 0.0,
            "ganado_afectado": 0.0}
    base.update(cambios)
    return base


def _medida(medidas, id_medida):
    return next(m for m in medidas.itertuples(index=False) if m.id_medida == id_medida)


def test_catalogo_valido_y_con_fuentes_registradas(medidas):
    assert restauracion.validar_medidas(medidas, registro.cargar_fuentes()) == []


def test_catalogo_incluye_una_medida_no_recomendada_y_una_hipotesis(medidas):
    niveles = set(medidas["nivel_sustento"])
    assert {"justificada", "condicionada", "hipotesis", "no_recomendada"} <= niveles


def test_fuente_inexistente_es_error(medidas):
    alterado = medidas.copy()
    alterado.loc[0, "fuentes"] = "F-9999"
    assert any("F-9999" in e for e in restauracion.validar_medidas(alterado, registro.cargar_fuentes()))


def test_no_recomendada_nunca_se_aplica(medidas):
    distrito = _distrito(ha_pajonal=500.0, ha_bofedal=100.0, ha_bosque=100.0)
    assert restauracion.aplicar_a_distrito(_medida(medidas, "R11"), distrito) is None


def test_ecosistema_por_debajo_del_umbral_no_activa_la_medida(medidas):
    assert restauracion.aplicar_a_distrito(_medida(medidas, "R01"), _distrito(ha_pajonal=2.0)) is None
    estado, motivo = restauracion.aplicar_a_distrito(_medida(medidas, "R01"), _distrito(ha_pajonal=400.0))
    assert estado == "aplica" and "no se sabe si fue el ecosistema quemado" in motivo


def test_medida_condicionada_o_hipotesis_queda_para_verificar(medidas):
    estado, _ = restauracion.aplicar_a_distrito(_medida(medidas, "R05"), _distrito(ha_bofedal=200.0))
    assert estado == "verificar en campo"


def test_erosion_sin_satelite_queda_pendiente(medidas):
    estado, motivo = restauracion.aplicar_a_distrito(_medida(medidas, "R03"), _distrito())
    assert estado == "verificar en campo" and "satelital pendiente" in motivo


def test_erosion_con_satelite_sin_pendiente_fuerte_no_aplica(medidas):
    assert restauracion.aplicar_a_distrito(_medida(medidas, "R03"), _distrito(), {"ha_quemado_pendiente_30": 0}) is None


def test_rehabilitacion_productiva_exige_perdidas_documentadas(medidas):
    con_perdidas = restauracion.aplicar_a_distrito(_medida(medidas, "R08"), _distrito(ganado_afectado=60.0))
    sin_perdidas = restauracion.aplicar_a_distrito(_medida(medidas, "R08"), _distrito(ha_zona_agricola=300.0))
    assert con_perdidas[0] == "aplica"
    assert sin_perdidas[0] == "verificar en campo" and "empadronar" in sin_perdidas[1]


RUTA = config.DIR_PROCESSED / "restauracion_medidas_distrito.csv"


@pytest.mark.skipif(not RUTA.exists(), reason="ejecute scripts/construir_matrices.py")
def test_tabla_procesada_no_recomienda_plantar_en_pajonales():
    tabla = pd.read_csv(RUTA, dtype={"ubigeo": str})
    assert "R11" not in set(tabla["id_medida"])
    assert set(tabla["estado_aplicacion"]) <= {"aplica", "verificar en campo"}
    # Las medidas condicionadas o hipotéticas nunca figuran como "aplica"
    dudosas = tabla[tabla["nivel_sustento"].isin(["condicionada", "hipotesis"])]
    assert (dudosas["estado_aplicacion"] == "verificar en campo").all()
