# Plan de trabajo

Plan aprobado el 21 de octubre de 2026. Fecha de corte inicial de la información: **21 de octubre de 2026**.

## Preguntas que guía el observatorio

1. ¿Qué comunidades y territorios han sido afectados por incendios forestales recientes?
2. ¿Qué daños humanos, ambientales y productivos se han documentado?
3. ¿Qué ayuda humanitaria se ha entregado y qué necesidades siguen pendientes?
4. ¿Dónde no existe información pública suficiente para confirmar la atención recibida?
5. ¿Qué intervenciones inmediatas podrían evaluarse?
6. ¿Qué acciones de recuperación y restauración corresponden a cada territorio?
7. ¿Qué recursos, presupuestos o donaciones podrían requerirse, según evidencia verificable?

## Alcance

| Dimensión | Definición |
|---|---|
| Territorio | Región Cusco (13 provincias) |
| Periodo prioritario | 1 de septiembre – 21 de octubre de 2026 (ampliable para contexto) |
| Unidad territorial | Centro poblado o comunidad si hay evidencia geográfica; si no, distrito o provincia |
| Horizontes | Atención inmediata: 0–90 días. Restauración: 3 meses – 5 años |

## Fases

| Fase | Contenido | Entregable verificable | Estado |
|---|---|---|---|
| 1 | Entorno, estructura, arquitectura, plan de investigación | `.venv` (Python 3.12), esquemas, validador, pruebas, esta documentación | Completa |
| 2 | Investigación documental | `data/raw/registro/*.csv` con fuentes, evidencias y vacíos de información; inventario consolidado de incendios | Completa |
| 3 | Análisis geoespacial (GEE + FIRMS) | Límites, focos de calor, severidad estimada e indicadores en `data/processed/` | En curso (límites, ecosistemas e indicadores listos; satélite requiere credenciales) |
| 4 | Dashboard Streamlit | `app.py` + `pages/` (paneles A–H) | Pendiente |
| 5 | Informe ejecutivo | `reports/informe_ejecutivo.md` | Pendiente |
| 6 | Pruebas, revisión y presentación | Suite completa, revisión cruzada de cifras, guion de presentación | Pendiente |

Al cierre de cada fase se reporta: qué funciona, qué datos están verificados, qué falta y cómo comprobarlo.

## Plan de investigación (Fase 2)

| Componente | Fuentes |
|---|---|
| Emergencias y daños | Reportes complementarios COEN/INDECI (gob.pe), SINPAD, COER Cusco, GORE Cusco, municipalidades, MIDAGRI/Agro Rural, CONIDA |
| Ayuda humanitaria | COEN/INDECI (bienes de ayuda humanitaria), GORE, municipalidades, Cruz Roja, Cáritas, donantes con anuncios verificables |
| Prensa (marcada como tal) | Andina, RPP, La República, Correo, Diario del Cusco, radios regionales |
| Territorio y población | Límites INEI (o GADM 4.1), centros poblados INEI 2017, SIGRID/CENEPRED |
| Satélite | NASA FIRMS; Earth Engine: Sentinel-2 SR + Cloud Score+, Landsat 8/9, MODIS MCD64A1, ESA WorldCover / Dynamic World, Copernicus DEM |
| Ecosistemas | Mapa Nacional de Ecosistemas del Perú (MINAM), Áreas Naturales Protegidas (SERNANP) |
| Restauración | Lineamientos SERFOR, guías MINAM, CONDESAN, Sierra Azul, literatura sobre pajonales y *Polylepis* |
| Costos | MEF Banco de Inversiones (IOARR), Consulta Amigable (PP 0068), SEACE, composición de bienes de ayuda humanitaria |

Estrategia de búsqueda: primero fuentes oficiales por provincia y fecha; luego prensa para identificar territorios no cubiertos por fuentes oficiales; cada pista de prensa se contrasta con al menos una búsqueda dirigida en fuentes oficiales antes de clasificarla.

## Bloqueos identificados en la Fase 1

| Bloqueo | Impacto | Mitigación |
|---|---|---|
| Earth Engine requiere proyecto Google Cloud y autenticación | Bloquea la Fase 3 | La usuaria autentica; el ID del proyecto va en `.env` (no versionado) |
| FIRMS requiere MAP_KEY | Bloquea la descarga de focos VIIRS | Clave gratuita; alternativa: FIRMS MODIS en Earth Engine (1 km) |
| Portal SINPAD respondió 404 (21-oct-2026) | Menos datos oficiales por evento | Usar reportes COEN en gob.pe; registrar la limitación |
| Geoserver SERFOR no respondió | Sin capas forestales SERFOR en línea | Reintentar; usar MINAM y Earth Engine |
| geoBoundaries no publica distritos de Perú | — | GADM 4.1 nivel 3 (descarga por script, no se redistribuye) o límites INEI |
| MCD64A1 tiene 1–2 meses de latencia; nubosidad creciente en octubre | Área quemada de octubre incompleta | Sentinel-2/Landsat con dNBR; declarar la incertidumbre |
