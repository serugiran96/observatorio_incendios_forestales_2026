# Criterios de verificación y trazabilidad

## Principio

Cada cifra que aparece en el dashboard o en el informe debe poder rastrearse hasta una fila de
`data/raw/registro/evidencias.csv` y, desde ella, hasta una fuente con enlace y fechas. No se
inventan cifras, testimonios, daños, donaciones, entregas, presupuestos ni ubicaciones.

## Estados de verificación

| Código | Etiqueta | Cuándo se usa |
|---|---|---|
| `dano_confirmado` | Daño confirmado | Fuente oficial primaria (COEN, INDECI, SINPAD, GORE, municipalidad) con dato específico, o dos fuentes independientes concordantes |
| `dano_reportado_pendiente` | Daño reportado pendiente de verificación | Reportado por prensa, redes institucionales sin documento oficial, o fuente única |
| `atencion_documentada` | Atención humanitaria documentada | Existe registro de una entrega o acción efectiva (no solo un anuncio) |
| `necesidad_pendiente_documentada` | Necesidad pendiente documentada | Una fuente documenta una necesidad no cubierta en su fecha de publicación |
| `atencion_no_verificada` | Atención no verificada | Ayuda anunciada o comprometida sin evidencia pública de entrega |
| `informacion_insuficiente` | Información insuficiente | La fuente es ambigua, no precisa lugar o fecha, o es contradictoria |

Para los eventos (`evento_incendio`), "confirmado" significa que el incendio figura en un registro
oficial; no implica que se conozca su extensión.

### Reglas de coherencia (validadas automáticamente)

- Una ayuda **anunciada** nunca puede marcarse como atención documentada.
- Los daños solo admiten `dano_confirmado`, `dano_reportado_pendiente` o `informacion_insuficiente`.
- Las necesidades solo admiten `necesidad_pendiente_documentada` o `informacion_insuficiente`.
- Toda afirmación puede marcarse como `informacion_insuficiente`.

### Ausencia de registros

**No encontrar registros públicos de ayuda no significa que una comunidad no la recibió.** En esos
casos el territorio se muestra como "atención no verificada" o "información insuficiente", y el
vacío se documenta en `vacios_informacion.csv` con las fuentes consultadas.

## Nivel de confianza

| Nivel | Criterio |
|---|---|
| Alta | Fuente oficial primaria con dato específico, o dos fuentes independientes concordantes |
| Media | Medio de comunicación reconocido que cita a una fuente oficial identificable |
| Baja | Fuente única no oficial, sin cita de origen, o dato ambiguo |

## Cifras contradictorias

Cuando dos fuentes dan cifras distintas para el mismo territorio y fecha, se registran **ambas**
como evidencias separadas. Las matrices derivadas muestran la cifra oficial más reciente y señalan la
discrepancia; nunca suman cifras de fuentes distintas.

## Precisión geográfica

Se registra el nivel más fino que la fuente permite (`punto`, `centro_poblado`, `distrito`,
`provincia`, `region`). No se georreferencian coordenadas que la fuente no da, salvo que el nombre
de la localidad sea inequívoco en el catálogo de centros poblados del INEI; en ese caso se indica en
`observaciones`.

## Datos personales

No se registran nombres, edades, DNI, teléfonos ni imágenes de personas damnificadas o fallecidas.
Las víctimas se registran solo como cifras. El validador rechaza textos con patrones de DNI o
celular.

## Criterios de atención inmediata (implementados en la Fase 4)

No hay ranking ni puntaje. Cada incendio del periodo prioritario lleva criterios verdadero/falso
(`src/observatorio/atencion.py`, `CRITERIOS`), visibles en la matriz y en el dashboard:

| Criterio | Grupo |
|---|---|
| Personas fallecidas o lesionadas | seguimiento humanitario |
| Personas damnificadas o viviendas inhabitables o destruidas | seguimiento humanitario |
| Cultivos o ganado perdidos o afectados | seguimiento humanitario |
| Damnificados sin entrega de BAH documentada | verificar atención |
| Lesionados sin atención médica documentada en el reporte | verificar atención |
| Abierto y sin actualización pública en más de 14 días (hasta la fecha de corte) | verificar atención |
| Tabla de daños ilegible, sin reporte COEN localizado o distrito por verificar | verificar atención |
| Abierto al último reporte; posible duplicado | contexto |

El estado de atención de cada incendio usa el vocabulario de los seis estados:

- **Atención humanitaria documentada:** el reporte o una evidencia del mismo distrito describe una
  entrega de BAH, atención médica o insumos pecuarios.
- **Atención no verificada:** hay daños a personas, viviendas o medios de vida y no se encontró
  registro público de atención. No significa que no hubo atención.
- **Necesidad pendiente documentada:** hay una solicitud de ayuda sin entrega posterior registrada.
- "Sin daños a personas reportados": solo daños a la cobertura; no requiere atención humanitaria.

La ayuda anunciada o entregada a nivel provincial se muestra rotulada como "nivel provincial, no
atribuible a este incendio" y no cambia el estado de atención. Los anuncios sin territorio se
muestran aparte. Las evidencias solo de prensa no generan filas: la matriz parte del inventario
oficial, y las cifras contradictorias se tratan como vacíos de información.
