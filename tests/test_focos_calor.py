"""Pruebas del procesamiento de focos de calor con un CSV ficticio en el formato de FIRMS.

Los focos de este archivo son inventados para ejercitar el código; no se guardan en data/.
"""

import io
from datetime import date

import pandas as pd

from observatorio import focos_calor, territorio

CSV_FICTICIO = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
-14.40,-71.50,340.1,0.4,0.4,2026-10-12,1805,N,VIIRS,h,2.0NRT,295.0,12.3,D
-14.41,-71.51,330.0,0.4,0.4,2026-10-13,0630,N,VIIRS,n,2.0NRT,290.0,4.1,N
-12.05,-77.04,330.0,0.4,0.4,2026-10-12,1805,N,VIIRS,l,2.0NRT,290.0,1.0,D
"""


def _focos():
    crudo = pd.read_csv(io.StringIO(CSV_FICTICIO)).assign(fuente_firms="VIIRS_SNPP_NRT")
    return focos_calor.normalizar(crudo)


def test_ventanas_respetan_el_maximo_de_dias():
    v = focos_calor.ventanas(date(2026, 9, 1), date(2026, 10, 21))
    assert v[0] == (date(2026, 9, 1), 10)
    assert sum(n for _, n in v) == 51
    assert all(n <= 10 for _, n in v)


def test_normalizar_hora_local_y_confianza():
    focos = _focos()
    # 18:05 UTC del 12-oct -> 13:05 hora de Perú; 06:30 UTC del 13-oct -> 01:30 del 13-oct
    assert focos.loc[0, "fecha_hora_local"] == pd.Timestamp("2026-10-12 13:05")
    assert focos.loc[1, "fecha_local"] == date(2026, 10, 13)
    assert list(focos["confianza"]) == ["alta", "nominal", "baja"]


def test_confianza_modis_numerica():
    crudo = pd.read_csv(io.StringIO(CSV_FICTICIO)).assign(fuente_firms="MODIS_NRT")
    crudo["confidence"] = [85, 50, 10]
    assert list(focos_calor.normalizar(crudo)["confianza"]) == ["alta", "nominal", "baja"]


def test_asignar_distritos_descarta_focos_fuera_de_cusco():
    focos = focos_calor.asignar_distritos(_focos(), territorio.cargar_distritos())
    assert len(focos) == 2  # el punto de Lima se descarta
    assert focos["ubigeo"].str.startswith("08").all()


def test_corroborar_por_distrito_y_ventana():
    focos = focos_calor.asignar_distritos(_focos(), territorio.cargar_distritos())
    ubigeo = focos["ubigeo"].iloc[0]
    inventario = pd.DataFrame([
        {"id_evento": "A", "ubigeo": ubigeo, "fecha_ocurrencia": "2026-10-12"},
        {"id_evento": "B", "ubigeo": ubigeo, "fecha_ocurrencia": "2026-09-01"},
        {"id_evento": "C", "ubigeo": "080101", "fecha_ocurrencia": "2026-10-12"},
    ])
    resultado = focos_calor.corroborar(inventario, focos).set_index("id_evento")
    assert resultado.loc["A", "focos_en_ventana"] == 2
    assert resultado.loc["B", "focos_en_ventana"] == 0
    assert resultado.loc["C", "corroboracion_satelital"] == "sin focos detectados"
