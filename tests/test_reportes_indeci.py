"""Pruebas de la interpretación de reportes COEN-INDECI (encabezados de daños y acciones)."""

import pytest

from observatorio import reportes_indeci as ri


@pytest.mark.parametrize(
    "encabezado, variable, unidad",
    [
        ("VIDA Y SALUD (PERSONA) DAMNIFICADA", "personas_damnificadas", "personas"),
        ("SALUD LESIONADA", "personas_lesionadas", "personas"),
        ("VIDA Y SALUD FALLECIDA", "personas_fallecidas", "personas"),
        ("VIDA Y SALUD (PERSONA) AFECTADA", "personas_afectadas", "personas"),
        ("DAÑOS VIVIENDA INHABITABLE", "viviendas_inhabitables", "viviendas"),
        ("VIVIENDA AFECTADA", "viviendas_afectadas", "viviendas"),
        ("VIVIENDA COLAPSADA", "viviendas_destruidas", "viviendas"),
        ("INFRAESTRUCTURA RIEGO MANGUERA DESTRUIDA (m)", "infraestructura_afectada", "m"),
        ("PRODUCCIÓN PECUARIA GANADERÍA PERDIDA", "ganado_perdido", "unidades"),
        ("PECUARIA GANADERÍA AFECTADA", "ganado_afectado", "unidades"),
        ("SECTORES DIVERSOS COBERTURA NATURAL DESTRUIDA (ha)", "cobertura_natural_destruida", "ha"),
        ("COBERTURA NATURAL AFECTADA (ha)", "cobertura_natural_afectada", "ha"),
        ("PRODUCCIÓN AGRÍCOLA CULTIVO PERDIDO (ha)", "cultivos_perdidos", "ha"),
    ],
)
def test_clasificar_encabezado(encabezado, variable, unidad):
    _, obtenida, unidad_obtenida = ri.clasificar_encabezado(encabezado)
    assert (obtenida, unidad_obtenida) == (variable, unidad)


def test_encabezado_desconocido_no_se_adivina():
    assert ri.clasificar_encabezado("de octubre las horas")[1] is None


@pytest.mark.parametrize(
    "texto, tipo",
    [
        ("Entregó Bienes de Ayuda Humanitaria (BAH) a las personas damnificadas", "entrega_bah"),
        ("Culminó la entrega de Bienes de Ayuda Humanitaria (BAH), para la persona damnificada", "entrega_bah"),
        ("Coordina internamente la entrega de Bienes de Ayuda Humanitaria (BAH), para las personas afectadas", "coordinacion_bah"),
        ("Brindó atención médica a las personas lesionadas, posteriormente fueron dadas de alta", "atencion_medica"),
        ("Realizó la entrega de insumos veterinarios a los productores", "insumos_pecuarios"),
        ("Solicitó apoyo con Bienes de Ayuda Humanitaria al Gobierno Regional", "solicitud_ayuda"),
        ("A las 00:10 horas, el incendio fue extinguido con la participación del personal de Serenazgo", "extincion"),
        ("La emergencia ha sido atendida, se procede al cierre del reporte", "cierre"),
        ("Se coordinó con la autoridad local a fin de que actualice la emergencia en el SINPAD", None),
    ],
)
def test_clasificar_accion(texto, tipo):
    assert ri.clasificar_accion(texto) == tipo


def test_coordinar_entrega_no_cuenta_como_entrega():
    # Un anuncio o coordinación nunca debe interpretarse como ayuda entregada
    assert ri.clasificar_accion("Coordina la entrega de BAH a las familias") != "entrega_bah"


@pytest.mark.parametrize(
    "descripcion, esperado",
    [
        ("causó daños a sectores diversos (cobertura natural) en el sector de Buena Vista, centro poblado Ccollana, "
         "distrito Velille, provincia de Chumbivilcas",
         ("sector de Buena Vista, centro poblado Ccollana", ["Velille"], "Chumbivilcas")),
        ("daños a sectores diversos (cobertura natural), en el sector de Chisicata, distrito y provincia de Espinar",
         ("sector de Chisicata", ["Espinar"], "Espinar")),
        ("daños a sectores diversos (cobertura natural) en los sectores de Erapata y Molonopata, distritos de Limatambo "
         "y Mollepata, provincia de Anta",
         ("sectores de Erapata y Molonopata", ["Limatambo", "Mollepata"], "Anta")),
        ("causó daños materiales (viviendas) en Limacniño, distrito de Pomacanchi, provincia de Acomayo",
         ("Limacniño", ["Pomacanchi"], "Acomayo")),
    ],
)
def test_ubicacion_desde_descripcion(descripcion, esperado):
    assert ri._ubicacion(descripcion) == esperado


def test_sectores_diversos_no_es_un_lugar():
    sector, _, _ = ri._ubicacion("causó daños a sectores diversos (cobertura natural), distrito de Layo, provincia de Canas")
    assert "diversos" not in sector


def test_cierre_temporal_no_es_emergencia_atendida():
    texto = "Se procede al cierre temporal del presente reporte debido a que la atención demorará más de lo previsto"
    assert ri.clasificar_accion(texto) == "cierre_temporal"


def test_acciones_de_bloque_con_entidad_ejecutora():
    bloque = """REGIONAL
Gobierno Regional de Cusco
El Centro de Operaciones de Emergencia Regional de Cusco, informó que:
• 16/10/2026
Municipalidad Distrital de Omacha
- Entregó Bienes de Ayuda Humanitaria (BAH) a las personas damnificadas.
• 25/9/2026
Puesto de Salud de Omacha
- Brindó atención médica a las personas lesionadas."""
    acciones = ri._acciones_de_bloque(bloque)
    resumen = [(a.entidad, a.tipo) for a in acciones]
    assert ("Municipalidad Distrital de Omacha", "entrega_bah") in resumen
    assert ("Puesto de Salud de Omacha", "atencion_medica") in resumen
