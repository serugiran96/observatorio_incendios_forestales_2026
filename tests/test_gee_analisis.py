"""Pruebas de la lógica pura del análisis satelital (sin conexión a Earth Engine)."""

import numpy as np
import pytest

from observatorio import gee_analisis as ga


def test_indices_con_valores_conocidos():
    # Vegetación sana: NIR alto, SWIR2 y rojo bajos
    assert ga.nbr(np.array([0.40]), np.array([0.10]))[0] == pytest.approx(0.6)
    assert ga.ndvi(np.array([0.40]), np.array([0.05]))[0] == pytest.approx(0.7778, abs=1e-4)


def test_quemado_reduce_nbr_y_da_dnbr_positivo():
    pre = ga.nbr(np.array([0.40]), np.array([0.10]))
    post = ga.nbr(np.array([0.15]), np.array([0.20]))  # tras el fuego: menos NIR, más SWIR
    dnbr = (pre - post)[0]
    assert dnbr > ga.UMBRAL_QUEMADO
    assert ga.clasificar_dnbr(dnbr) == "alta"


@pytest.mark.parametrize(
    "valor, clase",
    [(-0.3, "regeneración"), (0.0, "sin cambio"), (0.10, "baja"), (0.3, "moderada-baja"), (0.5, "moderada-alta"), (0.7, "alta")],
)
def test_clases_de_severidad_key_y_benson(valor, clase):
    assert ga.clasificar_dnbr(valor) == clase


def test_clases_contiguas_y_ordenadas():
    for (_, sup, _), (inf, _, _) in zip(ga.CLASES_SEVERIDAD, ga.CLASES_SEVERIDAD[1:]):
        assert sup == inf


def test_periodos_ordenados_y_sin_solaparse():
    p = ga.PERIODOS_TEMPORADA_2026
    assert p.pre_inicio < p.pre_fin < p.post_inicio < p.post_fin


def test_coberturas_excluidas_existen():
    assert set(ga.COBERTURAS_EXCLUIDAS) <= set(ga.COBERTURAS)
