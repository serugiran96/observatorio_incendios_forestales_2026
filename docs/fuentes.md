# Fuentes de información

Inventario de fuentes consultadas, cómo se procesan y sus limitaciones. El detalle de cada
documento (enlace, fechas, accesibilidad) está en `data/raw/registro/fuentes.csv`.

Fecha de consulta: 21 de octubre de 2026.

## 1. Fuentes oficiales procesadas automáticamente

### 1.1 Reportes diarios de emergencias – Oficina de Gestión del Riesgo de Desastres del Congreso

- **Qué es:** boletín diario que compila, en "tarjetas", emergencias reportadas por INDECI-COEN
  (fecha, ubicación y evaluación de daños).
- **Índice:** <https://www3.congreso.gob.pe/riesgodesastres/reportes/2026/>
- **Cobertura usada:** 28 reportes del 1-sep al 21-oct-2026 (n.º 162 a 194).
- **Proceso:** `scripts/extraer_reportes_emergencia.py` recorta cada tarjeta por coordenadas
  (`src/observatorio/reportes_emergencia.py`), interpreta los daños y genera filas `F-OGRD-*` y
  `E-OGRD-*` del registro, además de `data/processed/emergencias_cusco_ogrd.csv` para auditoría.
- **Resultado:** 98 incendios forestales distintos en Cusco con fecha de evento entre el 31-ago y
  el 20-oct-2026.
- **Limitaciones:**
  - **No es un inventario exhaustivo.** Es una selección diaria: por ejemplo, el incendio de Omacha
    (24-sep) figura en el COEN-INDECI pero no en estas tarjetas.
  - Faltan en el índice los reportes n.º 169 y 173–177 (aprox. 11–13 y 17–25 de septiembre).
  - Las cifras son evaluaciones preliminares (EDAN) informadas por autoridades locales.
    "Cobertura natural destruida" no es área quemada medida por satélite.
  - Los nombres de distrito tienen variantes ortográficas. Se normalizan con alias explícitos
    (`ALIAS_DISTRITOS`) que deben confirmarse contra los límites oficiales en la Fase 3.
  - Seis tarjetas se marcan como posible mismo incendio (misma provincia, ≤ 2 días, y lugar o cifra
    coincidentes). Se conservan todas y se señalan en `observaciones`.

### 1.2 Reportes del COEN-INDECI (fuente primaria)

- **Qué es:** reportes preliminares, complementarios (actualizaciones numeradas) e informes de
  emergencia del Centro de Operaciones de Emergencia Nacional. Cada uno incluye un PDF con hechos,
  ubicación (código SINPAD), evaluación de daños, acciones de respuesta (entrega de Bienes de Ayuda
  Humanitaria, atención médica, insumos veterinarios) y fuentes (COER Cusco, municipalidades).
- **Acceso:** <https://portal.indeci.gob.pe/emergencias/>. El listado web y su API no filtran de forma
  fiable, así que se usa el feed RSS con búsqueda (`/emergencias/feed/?s=incendio forestal cusco`),
  ordenado por fecha.
- **Proceso:** `scripts/indexar_reportes_indeci.py` → `data/processed/indice_reportes_indeci_cusco.csv`.
- **Resultado:** 191 reportes sobre 81 lugares de Cusco desde el 31-ago-2026.
- **Estado:** índice construido. La extracción del contenido de los PDF (daños y ayuda entregada) está
  en curso.
- **Limitaciones:** algunas tablas de daños tienen encabezados rotados que la extracción de texto no
  reconstruye. Esos valores se revisan manualmente o se registran como "cifra en PDF".

## 2. Fuentes consultadas manualmente

Notas de prensa y medios: se registran como `F-0001`, `F-0002`… en `fuentes.csv`. Los medios
se marcan como `medio_comunicacion` y sus cifras como "reportadas pendientes de verificación",
salvo que coincidan con una fuente oficial.

## 3. Fuentes no accesibles o con problemas (21-oct-2026)

| Fuente | Problema | Efecto |
|---|---|---|
| Portal SINPAD (`sinpad.indeci.gob.pe`) | HTTP 404 en las rutas probadas | Se usan los reportes COEN, que citan códigos SINPAD |
| Geoserver SERFOR | Sin respuesta (tiempo agotado) | Capas forestales SERFOR pendientes para la Fase 3 |
| LaPatilla (nota EFE del 11-oct) | HTTP 403 | No se usa como evidencia |
| Mercado Negro (nota de donaciones, 12-oct) | HTTP 403 | Canales de donación no verificados |
| Sitemap del portal INDECI | Redirige a otra página | Se usa el feed RSS |
| Panamericana (algunas notas) | Metadatos de fecha inválidos | La fecha se infiere del texto y se anota la incertidumbre |

## 4. Cifras regionales en disputa

Los acumulados regionales de 2026 difieren según la fuente y la fecha. Se registran todos como
evidencias de contexto, con su fuente, y ninguno se usa como total oficial:

| Fecha | Fuente | Incendios en el año | Hectáreas | Fallecidos |
|---|---|---|---|---|
| ~ago-2026 | Panamericana, citando a la Oficina Regional de GRD | 83 | ~1 500 | 2 |
| 08-oct | Canal N, citando a un vocero de la Oficina Regional de GRD | 283 | — | — |
| 09-oct | Canal N, citando al gobernador regional | — | 8 000 | 5 (primera semana de octubre) |
| 12-oct | Panamericana | 289 | — | 5 |
| 15-oct | Diario Correo | 340–350 | ~11 700 | 7 |
| 15-oct | Forbes Perú (Andina, Geresa, EFE) | — | — | 6 |
