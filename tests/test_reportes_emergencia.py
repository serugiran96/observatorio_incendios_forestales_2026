"""Pruebas del extractor de tarjetas de los reportes de emergencias (OGRD-Congreso).

Los textos reproducen el formato de las tarjetas, incluidos los defectos de extracción
observados (palabras pegadas, localidades partidas en varias líneas, tarjetas fusionadas).
"""

from datetime import date, datetime

import pandas as pd
import pytest

from observatorio import esquemas
from observatorio import evidencias as ev
from observatorio import reportes_emergencia as rem

TARJETA_SIMPLE = """CUSCO
Fecha: 20/10/26 16:30 h
EVENTO
• Incendio forestal.
UBICACIÓN
• Departamento: Cusco.
• Provincia: Canchis.
• Distrito: Sicuani/Sec. Lari
EVALUACIÓN DE DAÑOS
• Cobertura natural
destruida: 40 ha."""

TARJETA_LOCALIDAD_PARTIDA = """CUSCO
Fecha: 02/10/26 09:00 h
EVENTO
• Incendio forestal.
UBICACIÓN
• Departamento: Cusco.
• Provincia: Urubamba.
• Distritos: Urubamba/Sec.
• Huascaray, CP Yanahuara.
EVALUACIÓN DE DAÑOS
• 1 persona fallecida.
• Cobertura natural
destruida: 10 ha."""


def test_metadatos_desde_nombre_de_archivo():
    meta = rem.metadatos_archivo("reporteemergenciassismosfinal_194_211026.pdf")
    assert meta["numero_reporte"] == 194
    assert meta["fecha_reporte"] == date(2026, 10, 21)
    assert meta["url"].endswith("reporteemergenciassismosfinal_194_211026.pdf")


def test_metadatos_sin_numero():
    meta = rem.metadatos_archivo("reporteemergenciassismoscomplementario_010926.pdf")
    assert meta["numero_reporte"] is None
    assert meta["fecha_reporte"] == date(2026, 9, 1)


def test_parsear_tarjeta_simple():
    t = rem.parsear_tarjeta(TARJETA_SIMPLE)
    assert t.es_incendio_forestal
    assert t.fecha_hora == datetime(2026, 10, 20, 16, 30)
    assert (t.departamento, t.provincia, t.distrito, t.localidad) == ("Cusco", "Canchis", "Sicuani", "Sec. Lari")


def test_localidad_partida_en_varias_lineas():
    t = rem.parsear_tarjeta(TARJETA_LOCALIDAD_PARTIDA)
    assert t.distrito == "Urubamba"
    assert t.localidad == "Sec. Huascaray, CP Yanahuara"


def test_alias_de_provincia_y_palabras_pegadas():
    texto = TARJETA_SIMPLE.replace("Canchis", "Quispicanchis").replace("Sicuani/Sec. Lari", "SanPablo/Com. Chara")
    t = rem.parsear_tarjeta(texto)
    assert t.provincia == "Quispicanchi"
    assert t.distrito == "San Pablo"


def test_alias_de_distrito_conserva_nombre_reportado():
    t = rem.parsear_tarjeta(TARJETA_SIMPLE.replace("Sicuani/Sec. Lari", "Pichihua/Com. San Miguel"))
    assert t.distrito == "Pichigua"
    assert t.distrito_reportado == "Pichihua"


def test_limpieza_corta_tarjeta_fusionada_y_ruido():
    fusionada = TARJETA_SIMPLE + "\nOFICIALÍA\nMAYOR\nCUSCO\nFecha: 11/10/26 16:00 h\nEVENTO\n• Incendio forestal."
    limpio = rem.limpiar_texto_tarjeta(fusionada)
    assert "11/10/26" not in limpio
    assert "OFICIALÍA" not in limpio
    assert limpio.endswith("destruida: 40 ha.")


def test_evento_que_no_es_incendio_forestal():
    t = rem.parsear_tarjeta(TARJETA_SIMPLE.replace("Incendio forestal.", "Helada."))
    assert not t.es_incendio_forestal


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Cobertura nat. destruida:120 ha", {"cobertura_natural_destruida": 120.0}),
        ("Cobertura nat. destruida (35 ha).", {"cobertura_natural_destruida": 35.0}),
        ("Cobertura natural destruida: 3.5 ha", {"cobertura_natural_destruida": 3.5}),
        ("Cobertura nat. destruida:6ha", {"cobertura_natural_destruida": 6.0}),
        ("1 persona fallecida, 3 afectadas. ; 3 viviendas afectadas.",
         {"personas_fallecidas": 1.0, "personas_afectadas": 3.0, "viviendas_afectadas": 3.0}),
        ("1 vivienda con daños.", {"viviendas_afectadas": 1.0}),
        ("Ganadería perdida (30 u).", {"ganado_afectado": 30.0}),
    ],
)
def test_interpretar_danos_con_cifra(texto, esperado):
    obtenidos = {d.variable: d.valor for d in rem.interpretar_danos(texto) if d.valor is not None}
    assert obtenidos == esperado


def test_danos_sin_cifra_no_inventan_magnitudes():
    danos = rem.interpretar_danos("Personas afectadas/Viviendas afectadas. Cobertura natural destruida.")
    assert all(d.valor is None for d in danos)
    assert {d.categoria for d in danos} == {"dano_humano", "dano_vivienda_infraestructura", "dano_ambiental"}


def _emergencia(texto: str, archivo: str = "reporteemergenciassismosfinal_194_211026.pdf"):
    return (archivo, rem.metadatos_archivo(archivo)["fecha_reporte"], rem.parsear_tarjeta(texto))


def test_consolidar_conserva_la_version_mas_reciente():
    sin_cifra = TARJETA_SIMPLE.replace("Cobertura natural\ndestruida: 40 ha.", "Cobertura natural destruida.")
    emergencias = rem.consolidar(
        [
            _emergencia(TARJETA_SIMPLE, "reporteemergenciassismosfinal_194_211026.pdf"),
            _emergencia(sin_cifra, "reporteemergenciassismosfinal_193_201026.pdf"),
        ]
    )
    assert len(emergencias) == 1
    assert emergencias[0].archivo_ultimo.endswith("194_211026.pdf")
    assert "40 ha" in emergencias[0].tarjeta.texto_danos
    assert len(emergencias[0].reportes) == 2


def test_marca_posible_duplicado_por_misma_cifra_en_dias_consecutivos():
    otra = TARJETA_SIMPLE.replace("20/10/26 16:30", "21/10/26 09:00").replace("Sec. Lari", "Com. Otra")
    emergencias = rem.consolidar([_emergencia(TARJETA_SIMPLE), _emergencia(otra)])
    assert all(e.posibles_duplicados for e in emergencias)


def test_filas_evidencia_pasan_la_validacion():
    emergencias = rem.consolidar([_emergencia(TARJETA_LOCALIDAD_PARTIDA)])
    archivo = emergencias[0].archivo_ultimo
    fuentes = pd.DataFrame(
        [rem.fila_fuente(archivo, date(2026, 10, 21), "", "data/raw/documentos/x")], columns=esquemas.COLUMNAS_FUENTES
    )
    filas = pd.DataFrame(rem.filas_evidencia(emergencias[0]), columns=esquemas.COLUMNAS_EVIDENCIAS)
    resultado = ev.validar_evidencias(filas, fuentes)
    assert resultado.es_valido, resultado.resumen()
    assert set(filas["variable"]) == {"incendio_reportado", "personas_fallecidas", "cobertura_natural_destruida"}
    assert (filas["precision_geografica"] == "centro_poblado").all()
