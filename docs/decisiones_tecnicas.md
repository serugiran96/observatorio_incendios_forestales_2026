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

### DT-06 · Límites distritales (21-oct-2026)
geoBoundaries no publica distritos (ADM3) para Perú. Se priorizarán los límites oficiales del INEI; si
no son descargables de forma reproducible, se usará GADM 4.1 nivel 3. La licencia de GADM no permite
redistribuirlo, por lo que se descarga con un script y **no se versiona**.

### DT-07 · Sin ranking de "abandono" ni datos simulados (21-oct-2026)
La priorización se expresa con banderas explícitas y auditables (ver `criterios_verificacion.md`),
no con un puntaje compuesto. No se usan datos simulados en el dashboard: si un panel no tiene
evidencia, lo indica. Los datos ficticios solo existen dentro de `tests/`.

### DT-08 · Repositorio público (21-oct-2026)
El repositorio remoto es público. `.env`, credenciales de Google, descargas pesadas y rásteres están
excluidos en `.gitignore`. El registro no contiene datos personales (validado automáticamente).
