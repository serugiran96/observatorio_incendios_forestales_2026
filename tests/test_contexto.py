"""Verifica que las tablas de contexto transcritas (F-0019, MCLCP Cusco con datos del COER)
reproducen los totales publicados en el documento."""

import pandas as pd

from observatorio import config, esquemas

TOTALES_ANUALES_PUBLICADOS = {2020: 322, 2021: 330, 2022: 500, 2023: 370, 2024: 546}  # Cuadro N.° 03
TOTALES_PROVINCIA_PUBLICADOS = {2019: 351, 2020: 302, 2021: 330, 2022: 500, 2023: 370}  # Cuadro N.° 01


def test_serie_mensual_suma_los_totales_publicados():
    serie = pd.read_csv(config.DIR_RAW / "contexto" / "coer_incendios_mensuales_2020_2024.csv")
    assert serie.groupby("anio")["incendios"].sum().to_dict() == TOTALES_ANUALES_PUBLICADOS
    assert len(serie) == 60


def test_tabla_provincial_consistente():
    tabla = pd.read_csv(config.DIR_RAW / "contexto" / "coer_incendios_provincia_2019_2023.csv")
    assert set(tabla["provincia"]) == set(esquemas.PROVINCIAS_CUSCO)
    anios = ["2019", "2020", "2021", "2022", "2023"]
    assert (tabla[anios].sum(axis=1) == tabla["total"]).all()
    assert {int(a): tabla[a].sum() for a in anios} == TOTALES_PROVINCIA_PUBLICADOS
