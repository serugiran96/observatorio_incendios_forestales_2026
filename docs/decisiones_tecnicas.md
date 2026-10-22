# Decisiones técnicas

Registro breve de decisiones de arquitectura, con su motivo. Las más recientes van al final.

### DT-01 · Entorno con `uv` y Python 3.12 (21-oct-2026)
Se usa un `.venv` propio del proyecto creado con `uv` (Python 3.12.14 gestionado por uv). No se usa
el entorno base de Conda. `uv.lock` fija versiones exactas; `requirements.txt` se exporta desde el
lock para quien no use uv.

### DT-02 · Sin GDAL/rasterio ni geemap (21-oct-2026)
El procesamiento ráster (NDVI, NBR, dNBR, pendientes) se ejecuta en los servidores de Google Earth
Engine con `earthengine-api`; localmente solo se manejan vectores y tablas (geopandas con pyogrio,
que se instalan desde ruedas binarias). Se descarta `geemap` por su gran número de dependencias.

### DT-03 · Registro de evidencias en formato largo (21-oct-2026)
Cada fila es una afirmación de una fuente, con su estado de verificación y su confianza. Las
matrices de atención, restauración y presupuesto se **derivan** del registro por código; nunca se
editan a mano. Esto garantiza trazabilidad y permite registrar cifras contradictorias sin perderlas.

### DT-04 · El dashboard solo lee `data/processed/` (21-oct-2026)
Streamlit no llama a Earth Engine ni a APIs externas en tiempo de ejecución. Así funciona sin
conexión en una presentación, no expone credenciales y muestra siempre los mismos resultados para
una misma versión del repositorio.

### DT-05 · Proyección de igual área para superficies (21-oct-2026)
Cusco cruza las zonas UTM 18S y 19S. Las áreas se calculan en *South America Albers Equal Area
Conic* (`ESRI:102033`); los datos se almacenan en WGS84 (`EPSG:4326`).

### DT-06 · Límites distritales (21-oct-2026, actualizada)
geoBoundaries no publica distritos (ADM3) para Perú y GADM 4.1 está desactualizado y no tiene UBIGEO.
Se usan los límites del servicio de cartografía de OSINERGMIN (UBIGEO INEI, 112 distritos de Cusco,
población 2018), descargados con `scripts/descargar_limites.py`.

### DT-07 · Sin ranking de "abandono" ni datos simulados (21-oct-2026)
La priorización se expresa con banderas explícitas y auditables (ver `criterios_verificacion.md`),
no con un puntaje compuesto. No se usan datos simulados en el dashboard: si un panel no tiene
evidencia, lo indica. Los datos ficticios solo existen dentro de `tests/`.

### DT-08 · Repositorio público (21-oct-2026)
El repositorio remoto es público. `.env`, credenciales de Google, descargas pesadas y rásteres están
excluidos en `.gitignore`. El registro no contiene datos personales (validado automáticamente).

### DT-09 · Entorno virtual fuera de la sincronización de iCloud (21-oct-2026)
La carpeta `~/Documents` de este equipo se sincroniza con iCloud Drive, que marca como ocultos
(`chflags hidden`) los archivos dentro de carpetas que empiezan con punto, como `.venv`. Python 3.12.14
ignora los archivos `.pth` ocultos, lo que rompía la instalación editable del paquete. Además, sincronizar
miles de archivos del entorno con iCloud es lento y arriesgado. El entorno real vive en `venv.nosync/`
(iCloud no sincroniza carpetas con sufijo `.nosync`) y `.venv` es un enlace simbólico a él, de modo que
`uv run` y `uv sync` funcionan sin configuración adicional. Ambos están en `.gitignore`.

### DT-10 · Extracción de reportes PDF por coordenadas (21-oct-2026)
Los reportes del Congreso presentan las emergencias en tarjetas de varias columnas que se superponen
en vertical. La extracción de texto plano mezcla columnas, así que cada tarjeta se recorta desde su
encabezado (detectado sobre la palabra "EVENTO") hasta el encabezado de la siguiente tarjeta de la
misma columna. El ancho se limita por la columna siguiente. La interpretación de daños nunca inventa
magnitudes: si no hay cifra, se registra una descripción cualitativa.

### DT-11 · Índice del COEN-INDECI desde el feed RSS (21-oct-2026)
El listado web de emergencias de INDECI y su API REST no filtran de forma fiable por región y tipo. El
feed RSS con parámetro de búsqueda sí lo hace y está ordenado por fecha, lo que permite un índice
reproducible que se detiene al llegar al inicio del periodo.

### DT-12 · Ecosistemas por servicio de mapas (21-oct-2026)
El Mapa Nacional de Ecosistemas se distribuye como un archivo nacional de 1,24 GB. Se consulta el
servicio REST del MINAM solo para la caja de Cusco, por páginas y con geometría generalizada (~50 m).
La paginación avanza por desplazamiento hasta el total informado por el servicio, porque algunas
páginas devuelven menos registros que su tamaño (geometrías nulas).

### DT-13 · Atribución del cambio de vegetación a fuego (21-oct-2026)
Una caída del NBR no prueba un incendio. Solo se llama "área quemada probable" al cambio que coincide
con focos de calor a ≤ 1,5 km en el periodo; el resto se informa como "cambio no atribuido". Los
focos de calor tampoco se convierten en hectáreas: se usan solo para corroborar.
