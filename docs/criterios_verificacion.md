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

## Banderas de atención (Fase 4)

En lugar de un ranking o puntaje de "abandono", cada territorio mostrará banderas explícitas, cada
una con su motivo y las evidencias que la activan, por ejemplo:

- Daño humano reportado (fallecidos o lesionados).
- Necesidad documentada sin evidencia posterior de atención.
- Fuentes de agua, viviendas o medios de vida afectados.
- Evidencia solo de prensa (requiere verificación oficial).
- Más de N días sin actualización desde el evento.
- Fuentes contradictorias.

Las banderas distinguen entre "requiere verificación" y "posible atención urgente"; no se combinan
en un puntaje único.
