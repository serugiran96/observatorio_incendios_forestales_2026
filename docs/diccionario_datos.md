# Diccionario de datos

Los vocabularios controlados están definidos en `src/observatorio/esquemas.py`, y
`scripts/validar_registro.py` los verifica. Las fechas usan el formato `AAAA-MM-DD`.

## `data/raw/registro/fuentes.csv`

Una fila por documento, página o conjunto de datos consultado.

| Columna | Descripción |
|---|---|
| `id_fuente` | Identificador único (ej. `F-0001`) |
| `institucion` | Institución o medio que publica |
| `titulo` | Título del documento o nota |
| `url` | Enlace original |
| `tipo_fuente` | `oficial_nacional`, `oficial_regional`, `oficial_local`, `medio_comunicacion`, `tecnica_academica`, `satelital`, `sociedad_civil`, `otra` |
| `fecha_publicacion` | Fecha de publicación indicada por la fuente |
| `fecha_consulta` | Fecha en que se consultó |
| `accesible` | `si`, `parcial` o `no` (las fuentes inaccesibles también se registran) |
| `archivo_local` | Ruta a la copia descargada en `data/raw/documentos/`, si existe |
| `notas` | Limitaciones, contexto, problemas de acceso |

## `data/raw/registro/evidencias.csv`

Una fila por afirmación extraída de una fuente.

| Columna | Descripción |
|---|---|
| `id_evidencia` | Identificador único (ej. `E-0001`) |
| `id_fuente` | Referencia a `fuentes.csv` |
| `fecha_evento` | Fecha del hecho (inicio del incendio, entrega de ayuda, etc.) |
| `provincia`, `distrito`, `localidad` | Ubicación con el detalle que la fuente permite |
| `ubigeo` | Código INEI de 6 dígitos (`08XXXX`), si se conoce |
| `latitud`, `longitud` | Coordenadas WGS84, solo si la fuente las da o la localidad es inequívoca |
| `precision_geografica` | `punto`, `centro_poblado`, `distrito`, `provincia`, `region` |
| `categoria` | Tipo de afirmación (ver tabla siguiente) |
| `variable` | Variable controlada o `descripcion_cualitativa` |
| `valor`, `unidad` | Cifra y unidad, si la afirmación es cuantitativa |
| `descripcion` | Paráfrasis o cita breve, sin datos personales |
| `estado_verificacion` | Uno de los seis estados (ver `criterios_verificacion.md`) |
| `nivel_confianza` | `alta`, `media`, `baja` |
| `fuente_oficial_citada` | Si un medio cita a una entidad oficial, cuál |
| `observaciones` | Discrepancias, supuestos o notas de georreferenciación |

### Categorías y variables

| Categoría | Variables |
|---|---|
| `evento_incendio` | `incendio_reportado`, `incendio_activo`, `incendio_controlado`, `incendio_extinguido`, `numero_incendios`, `numero_emergencias` |
| `dano_humano` | `personas_fallecidas`, `personas_lesionadas`, `personas_afectadas`, `personas_damnificadas`, `familias_afectadas` |
| `dano_vivienda_infraestructura` | `viviendas_afectadas`, `viviendas_destruidas`, `infraestructura_afectada` |
| `dano_ambiental` | `superficie_afectada`, `cobertura_natural_afectada`, `fuentes_agua_afectadas`, `fauna_afectada` |
| `dano_productivo` | `cultivos_afectados`, `pastos_afectados`, `ganado_afectado`, `plantaciones_forestales_afectadas` |
| `necesidad` | `necesidad_reportada` |
| `ayuda_anunciada` | `ayuda_anunciada` |
| `ayuda_entregada` | `bienes_ayuda_entregados`, `familias_atendidas` |
| `respuesta_operativa` | `personal_desplegado`, `aeronaves_desplegadas`, `presupuesto_asignado` |
| `contexto` | Solo `descripcion_cualitativa` |

`descripcion_cualitativa` se admite en cualquier categoría para afirmaciones sin cifra.

## `data/raw/registro/vacios_informacion.csv`

Una fila por vacío de información detectado (pregunta 4 del observatorio).

| Columna | Descripción |
|---|---|
| `id_vacio` | Identificador único (ej. `V-0001`) |
| `tema` | Qué información falta (ej. "entrega de ayuda", "extensión del daño") |
| `provincia`, `distrito` | Territorio al que aplica (vacío si es regional) |
| `descripcion` | Qué se buscó y qué no se encontró |
| `fuentes_consultadas` | IDs de fuentes revisadas o sitios consultados sin resultado |
| `fecha_registro` | Fecha en que se documentó el vacío |
| `accion_sugerida` | Cómo podría cerrarse (solicitud de información, verificación en campo...) |
