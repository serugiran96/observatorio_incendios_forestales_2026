"""Esquemas de datos: columnas, vocabularios controlados y reglas de coherencia.

El registro de evidencias usa formato "largo": cada fila es UNA afirmación extraída de UNA
fuente (por ejemplo, "COEN reporta 120 ha afectadas en el distrito X al 10-oct"). Las matrices
del dashboard se derivan de este registro, nunca se escriben a mano.
"""

from __future__ import annotations

# --- Territorio -----------------------------------------------------------------
PROVINCIAS_CUSCO = (
    "Acomayo",
    "Anta",
    "Calca",
    "Canas",
    "Canchis",
    "Chumbivilcas",
    "Cusco",
    "Espinar",
    "La Convención",
    "Paruro",
    "Paucartambo",
    "Quispicanchi",
    "Urubamba",
)

PRECISIONES_GEOGRAFICAS = {
    "punto": "Coordenadas reportadas por la fuente o georreferenciadas desde un lugar inequívoco",
    "centro_poblado": "Comunidad, anexo o centro poblado identificado por nombre",
    "distrito": "Solo se conoce el distrito",
    "provincia": "Solo se conoce la provincia",
    "region": "Dato agregado para toda la región Cusco",
}

# --- Fuentes --------------------------------------------------------------------
TIPOS_FUENTE = {
    "oficial_nacional": "Entidad pública nacional (INDECI, COEN, SERFOR, MINAM, MIDAGRI, CONIDA...)",
    "oficial_regional": "Gobierno Regional del Cusco, COER Cusco, direcciones regionales",
    "oficial_local": "Municipalidad provincial o distrital",
    "medio_comunicacion": "Medio de comunicación (agencia, diario, radio, televisión)",
    "tecnica_academica": "Documento técnico, científico o académico",
    "satelital": "Producto satelital o geoespacial (FIRMS, Sentinel-2, MODIS...)",
    "sociedad_civil": "ONG, cooperación, iglesia u organización comunal",
    "otra": "Otra procedencia (se explica en notas)",
}

ACCESIBILIDAD_FUENTE = ("si", "parcial", "no")

# --- Evidencias -----------------------------------------------------------------
# Los seis estados exigidos por el proyecto. La ausencia de registros NO equivale a
# "no recibió ayuda": en ese caso corresponde "atencion_no_verificada" o "informacion_insuficiente".
ESTADOS_VERIFICACION = {
    "dano_confirmado": "Daño confirmado",
    "dano_reportado_pendiente": "Daño reportado pendiente de verificación",
    "atencion_documentada": "Atención humanitaria documentada",
    "necesidad_pendiente_documentada": "Necesidad pendiente documentada",
    "atencion_no_verificada": "Atención no verificada",
    "informacion_insuficiente": "Información insuficiente",
}

CATEGORIAS_EVIDENCIA = {
    "evento_incendio": "Ocurrencia, estado o conteo de incendios",
    "dano_humano": "Personas fallecidas, lesionadas, afectadas o damnificadas (solo cifras)",
    "dano_vivienda_infraestructura": "Viviendas, infraestructura o servicios afectados",
    "dano_ambiental": "Cobertura vegetal, suelos, fuentes de agua o fauna afectada",
    "dano_productivo": "Cultivos, pastos, ganado u otros medios de vida afectados",
    "necesidad": "Necesidad humanitaria o de recuperación documentada",
    "ayuda_anunciada": "Ayuda comprometida o anunciada, sin evidencia de entrega",
    "ayuda_entregada": "Entrega de ayuda respaldada por una fuente",
    "respuesta_operativa": "Combate del fuego: brigadas, aeronaves, equipos",
    "contexto": "Información de contexto (causas, condiciones, acumulados)",
}

_ESTADOS_DANO = frozenset({"dano_confirmado", "dano_reportado_pendiente", "informacion_insuficiente"})
_ESTADOS_ATENCION = frozenset({"atencion_documentada", "atencion_no_verificada", "informacion_insuficiente"})

# Coherencia entre la categoría de la afirmación y su estado de verificación.
ESTADOS_PERMITIDOS_POR_CATEGORIA = {
    "evento_incendio": _ESTADOS_DANO,
    "dano_humano": _ESTADOS_DANO,
    "dano_vivienda_infraestructura": _ESTADOS_DANO,
    "dano_ambiental": _ESTADOS_DANO,
    "dano_productivo": _ESTADOS_DANO,
    "necesidad": frozenset({"necesidad_pendiente_documentada", "informacion_insuficiente"}),
    "ayuda_anunciada": frozenset({"atencion_no_verificada", "informacion_insuficiente"}),
    "ayuda_entregada": _ESTADOS_ATENCION,
    "respuesta_operativa": _ESTADOS_ATENCION,
    "contexto": _ESTADOS_DANO,
}

NIVELES_CONFIANZA = {
    "alta": "Fuente oficial primaria con dato específico, o dos fuentes independientes concordantes",
    "media": "Medio de comunicación reconocido que cita a una fuente oficial identificable",
    "baja": "Fuente única no oficial, sin cita de origen, o dato ambiguo",
}

# Variable registrada -> categoría a la que pertenece. "descripcion_cualitativa" sirve para
# afirmaciones sin cifra en cualquier categoría.
VARIABLE_CUALITATIVA = "descripcion_cualitativa"
VARIABLES = {
    # Eventos
    "incendio_reportado": "evento_incendio",
    "incendio_activo": "evento_incendio",
    "incendio_controlado": "evento_incendio",
    "incendio_extinguido": "evento_incendio",
    "numero_incendios": "evento_incendio",
    "numero_emergencias": "evento_incendio",
    # Daño humano (solo cifras agregadas; nunca nombres)
    "personas_fallecidas": "dano_humano",
    "personas_lesionadas": "dano_humano",
    "personas_afectadas": "dano_humano",
    "personas_damnificadas": "dano_humano",
    "personas_desaparecidas": "dano_humano",
    "familias_afectadas": "dano_humano",
    # Vivienda e infraestructura
    "viviendas_afectadas": "dano_vivienda_infraestructura",
    "viviendas_destruidas": "dano_vivienda_infraestructura",
    "viviendas_inhabitables": "dano_vivienda_infraestructura",
    "infraestructura_afectada": "dano_vivienda_infraestructura",
    # Ambiental ("destruida"/"afectada" siguen la terminología de INDECI; no es área quemada medida)
    "superficie_afectada": "dano_ambiental",
    "cobertura_natural_destruida": "dano_ambiental",
    "cobertura_natural_afectada": "dano_ambiental",
    "fuentes_agua_afectadas": "dano_ambiental",
    "fauna_afectada": "dano_ambiental",
    # Productivo
    "cultivos_afectados": "dano_productivo",
    "cultivos_perdidos": "dano_productivo",
    "pastos_afectados": "dano_productivo",
    "ganado_afectado": "dano_productivo",
    "ganado_perdido": "dano_productivo",
    "plantaciones_forestales_afectadas": "dano_productivo",
    # Necesidades y atención
    "necesidad_reportada": "necesidad",
    "ayuda_anunciada": "ayuda_anunciada",
    "bienes_ayuda_entregados": "ayuda_entregada",
    "entrega_bah": "ayuda_entregada",  # entrega de Bienes de Ayuda Humanitaria reportada en SINPAD/COEN
    "atencion_medica": "ayuda_entregada",
    "insumos_pecuarios": "ayuda_entregada",  # insumos veterinarios, forraje, semillas
    "familias_atendidas": "ayuda_entregada",
    "personal_desplegado": "respuesta_operativa",
    "accion_respuesta": "respuesta_operativa",
    "aeronaves_desplegadas": "respuesta_operativa",
    "presupuesto_asignado": "respuesta_operativa",
}

# Etiquetas legibles de las variables (informe y dashboard)
ETIQUETAS_VARIABLES = {
    "incendio_reportado": "Incendio reportado",
    "incendio_activo": "Incendio activo",
    "incendio_controlado": "Incendio controlado",
    "incendio_extinguido": "Incendio extinguido",
    "numero_incendios": "Número de incendios",
    "numero_emergencias": "Número de emergencias",
    "personas_fallecidas": "Personas fallecidas",
    "personas_lesionadas": "Personas lesionadas",
    "personas_afectadas": "Personas afectadas",
    "personas_damnificadas": "Personas damnificadas",
    "personas_desaparecidas": "Personas desaparecidas",
    "familias_afectadas": "Familias afectadas",
    "viviendas_afectadas": "Viviendas afectadas",
    "viviendas_inhabitables": "Viviendas inhabitables",
    "viviendas_destruidas": "Viviendas destruidas o colapsadas",
    "infraestructura_afectada": "Infraestructura afectada",
    "superficie_afectada": "Superficie afectada",
    "cobertura_natural_destruida": "Cobertura natural destruida",
    "cobertura_natural_afectada": "Cobertura natural afectada",
    "fuentes_agua_afectadas": "Fuentes de agua afectadas",
    "fauna_afectada": "Fauna afectada",
    "cultivos_afectados": "Cultivos afectados",
    "cultivos_perdidos": "Cultivos perdidos",
    "pastos_afectados": "Pastos afectados",
    "ganado_afectado": "Ganado afectado",
    "ganado_perdido": "Ganado perdido",
    "plantaciones_forestales_afectadas": "Plantaciones forestales afectadas",
    "necesidad_reportada": "Necesidad reportada",
    "ayuda_anunciada": "Ayuda anunciada o en coordinación",
    "bienes_ayuda_entregados": "Bienes de ayuda entregados",
    "entrega_bah": "Entrega de Bienes de Ayuda Humanitaria",
    "atencion_medica": "Atención médica",
    "insumos_pecuarios": "Insumos o atención pecuaria",
    "familias_atendidas": "Familias atendidas",
    "personal_desplegado": "Personal desplegado",
    "aeronaves_desplegadas": "Aeronaves desplegadas",
    "presupuesto_asignado": "Presupuesto asignado",
    "accion_respuesta": "Acción de respuesta",
    VARIABLE_CUALITATIVA: "Descripción cualitativa",
}

# --- Columnas de los archivos del registro --------------------------------------
COLUMNAS_FUENTES = (
    "id_fuente",
    "institucion",
    "titulo",
    "url",
    "tipo_fuente",
    "fecha_publicacion",
    "fecha_consulta",
    "accesible",
    "archivo_local",
    "notas",
)

COLUMNAS_EVIDENCIAS = (
    "id_evidencia",
    "id_fuente",
    "fecha_evento",
    "provincia",
    "distrito",
    "localidad",
    "ubigeo",
    "latitud",
    "longitud",
    "precision_geografica",
    "categoria",
    "variable",
    "valor",
    "unidad",
    "descripcion",
    "estado_verificacion",
    "nivel_confianza",
    "fuente_oficial_citada",
    "observaciones",
)

COLUMNAS_VACIOS = (
    "id_vacio",
    "tema",
    "provincia",
    "distrito",
    "descripcion",
    "fuentes_consultadas",
    "fecha_registro",
    "accion_sugerida",
)

# Columnas que no pueden quedar vacías en cada archivo
OBLIGATORIAS_FUENTES = ("id_fuente", "institucion", "titulo", "tipo_fuente", "fecha_consulta", "accesible")
# provincia/distrito/localidad se exigen según la precisión geográfica (ver evidencias.py)
OBLIGATORIAS_EVIDENCIAS = (
    "id_evidencia",
    "id_fuente",
    "precision_geografica",
    "categoria",
    "variable",
    "descripcion",
    "estado_verificacion",
    "nivel_confianza",
)
