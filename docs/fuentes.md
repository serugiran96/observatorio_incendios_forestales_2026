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
  emergencia del Centro de Operaciones de Emergencia Nacional. Cada PDF incluye:
  1. hechos: fecha y hora de ocurrencia, descripción y lugar;
  2. ubicación, a veces con código SINPAD;
  3. tabla de daños (EDAN);
  4. acciones de respuesta: entregas de Bienes de Ayuda Humanitaria (BAH), atención médica,
     insumos veterinarios, extinción y cierre;
  5. fuentes (COER Cusco, municipalidades);
  6. anexos con los BAH entregados y la cronología completa de acciones.
- **Acceso:** <https://portal.indeci.gob.pe/emergencias/>. El listado web y su API no filtran de forma
  fiable, así que se usa el feed RSS con búsqueda (`/emergencias/feed/?s=incendio forestal cusco`),
  ordenado por fecha.
- **Proceso:**
  - `scripts/indexar_reportes_indeci.py --descargar` genera el índice y descarga los PDF. Cada PDF se
    elige porque su nombre contiene el número del reporte, ya que la página enlaza también reportes
    de otras regiones.
  - `src/observatorio/reportes_indeci.py` interpreta cada PDF:
    - encabezados de la tabla de daños reconstruidos por posición;
    - lectura horizontal forzada de caracteres que el PDF marca como rotados;
    - acciones tomadas de la sección 4.2 y del anexo de cronología.
  - `scripts/extraer_reportes_indeci.py` agrupa los reportes de un mismo incendio (lugar y fecha de
    ocurrencia), toma los daños de la última actualización y las acciones de toda la cadena. Genera
    filas `F-INDECI-*` y `E-INDECI-*`, `incendios_cusco_consolidado.csv` y `acciones_respuesta_indeci.csv`.
- **Privacidad:** no se procesa la sección "Detalle de daños a la salud de las personas" (edad, sexo,
  lesión) ni las firmas del "Control de cambios".
- **Limitaciones:**
  - El feed suele devolver solo la última actualización de cada incendio. La cronología de acciones
    compensa parcialmente esa falta.
  - "Abierto al último reporte" significa que el cierre no consta en los reportes indexados.
  - Las cantidades de los anexos de BAH (rubros, pesos) no se leen de forma fiable; solo se registra
    qué rubros se entregaron.
  - 2 de los 191 reportes indexados no tienen su PDF enlazado en el portal (N.º 14122 Livitaca y
    N.º 14533 Ccapi); se registran como vacíos V-0015 y V-0016. Resultado final: 189 reportes leídos,
    179 incendios COEN-INDECI + 2 que solo figuran en las tarjetas OGRD = 181 incendios.
  - Se detectó una errata del propio INDECI: el reporte de Sicuani se publica como N.º 13371 pero el
    PDF dice N.º 13372. Se anota en `fuentes.csv`.

### 1.3 Contexto histórico (2019–2024)

`data/raw/contexto/` contiene dos tablas transcritas del reporte de la Mesa de Concertación para la
Lucha contra la Pobreza – Cusco (F-0019, enero de 2026), que cita al COER Cusco:

- `coer_incendios_mensuales_2020_2024.csv`: incendios por mes (cuadro N.° 03). Muestra la
  estacionalidad: los picos son agosto, septiembre y octubre (en 2024: 115, 138 y 156).
- `coer_incendios_provincia_2019_2023.csv`: incendios por provincia y año (cuadro N.° 01).

`tests/test_contexto.py` verifica que las tablas reproducen los totales publicados. El documento
tiene una inconsistencia interna: 2020 suma 322 incendios en la serie mensual y 302 en la tabla
provincial. Se conservan ambas cifras tal como fueron publicadas.

### 1.4 Capas geográficas

| Capa | Fuente | Acceso | Notas |
|---|---|---|---|
| Límites distritales (112 distritos, UBIGEO, población 2018) | OSINERGMIN, servicio "Límites distritales del Perú" (INEI) | REST, consulta por departamento 08 | Se versiona la versión simplificada (~100 m); la completa queda en `data/raw/geodatos/` |
| Ecosistemas (24 tipos en Cusco) | MINAM, Mapa Nacional de Ecosistemas del Perú (2018) | REST `ServicioEcosistemas_MINAM`, por páginas | 16 473 polígonos generalizados a ~50 m; cubren el 99,6 % de la región; la capa del mapa se simplifica a ~400 m |
| GADM 4.1 | gadm.org | Descartado | Sin UBIGEO y desactualizado (10 distritos en La Convención frente a 14 oficiales) |

### 1.5 Referencias técnicas para restauración y competencias

Registradas en `fuentes.csv` (`F-0020`–`F-0029`) y citadas por el catálogo de medidas:

| ID | Referencia | Uso |
|---|---|---|
| F-0020 | SERFOR (2018), lineamientos de restauración (R.D.E. 083-2018) | Definición y principios; PDF no accesible (HTTP 403) |
| F-0021 | SERFOR (2019), principios y opciones de restauración | Opciones: prevención, manejo de regeneración natural, plantaciones |
| F-0022 | Román et al. (2025), boletín IGP; Roman et al. (2024), *Fire* | Recuperación de pastizales quemados en Calca y Quispicanchi |
| F-0023 | Estudio de Chiara, Ayacucho (2023) | Rebrote predominante en pajonal; 4-5 años |
| F-0024 | Román-Cuesta et al. (2011) | Turba y rebrote en bosques montanos del sur del Perú (solo resumen) |
| F-0025 | Caretas (2024), cita a SERFOR | Técnicas post-incendio de SERFOR |
| F-0026 | MITECO (2026), Miño-Sil | Fajinas, albarradas y mulching (contexto español) |
| F-0027 | FUEGORED (2010) | Emergencia antes de las primeras lluvias |
| F-0028 | El Peruano (2022), queuña en Ollantaytambo | Viveros comunales de especies nativas |
| F-0029 | INDECI (2026), presentación al Congreso | Niveles de emergencia y quién entrega BAH |

No se encontró evidencia publicada sobre la recuperación de bofedales quemados ni costos unitarios
verificables para las intervenciones; ambos vacíos se reflejan en el catálogo ("hipótesis") y en
la matriz de presupuesto ("pendiente de cotización").

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
| PDF de lineamientos SERFOR (`serfor.gob.pe`) y repositorio SERFOR | HTTP 403 / sin respuesta | Contenido tomado de la presentación F-0021 |

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
