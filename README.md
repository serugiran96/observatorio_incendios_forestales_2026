# Cusco — del incendio a la recuperación

Observatorio territorial de los incendios forestales en la región Cusco, Perú (septiembre–octubre
de 2026). El proyecto reúne evidencia documental y satelital para responder qué territorios fueron
afectados, qué daños y necesidades están documentados, qué atención consta públicamente, dónde
falta información, y qué intervenciones inmediatas y de restauración podrían evaluarse.

> **Fecha de corte inicial:** 21 de octubre de 2026.
> Proyecto universitario. No reemplaza los registros oficiales de INDECI, COEN ni del Gobierno
> Regional del Cusco.

## Principios

- **Trazabilidad:** cada cifra remite a una evidencia y cada evidencia a una fuente con enlace y fechas.
- **Sin evidencia inventada:** no se crean cifras, entregas, donaciones, presupuestos ni ubicaciones.
- **Seis estados de verificación**, que distinguen daño confirmado, daño reportado, atención
  documentada, necesidad pendiente, atención no verificada e información insuficiente.
- **Que falte un registro no prueba que falte la ayuda:** no se concluye que una comunidad no
  recibió ayuda solo porque no se encontraron registros públicos.
- **Sin datos personales** de personas damnificadas o fallecidas.

Detalle en [`docs/criterios_verificacion.md`](docs/criterios_verificacion.md).

## Estado del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Entorno, estructura, esquemas y plan | Completa |
| 2 | Investigación documental y registro de evidencias | Completa (inventario al 21-oct-2026) |
| 3 | Análisis geoespacial (Earth Engine, FIRMS) | En curso: límites, ecosistemas e indicadores listos; satélite pendiente de credenciales |
| 4 | Dashboard Streamlit | Pendiente |
| 5 | Informe ejecutivo | Pendiente |
| 6 | Pruebas finales y presentación | Pendiente |

Ver [`docs/plan_de_trabajo.md`](docs/plan_de_trabajo.md).

## Estructura

```
├── app.py                  # Dashboard Streamlit (Fase 4)
├── src/observatorio/       # Funciones reutilizables
│   ├── config.py           #   rutas, fecha de corte, sistemas de referencia
│   ├── esquemas.py         #   columnas, vocabularios y reglas de coherencia
│   ├── evidencias.py       #   carga, validación y escritura del registro
│   ├── reportes_emergencia.py  # extracción de los reportes diarios OGRD-Congreso (PDF)
│   ├── reportes_indeci.py      # extracción de los reportes COEN-INDECI (PDF)
│   ├── territorio.py           # límites oficiales y asignación de UBIGEO
│   ├── focos_calor.py          # NASA FIRMS: descarga, limpieza y corroboración
│   └── gee_analisis.py         # Earth Engine: NBR/dNBR, severidad, área quemada probable
├── scripts/                # Procesos ejecutables (validación, descargas, análisis)
├── data/
│   ├── raw/registro/       # fuentes.csv, evidencias.csv, vacios_informacion.csv (versionados)
│   ├── raw/documentos/     # copias de documentos fuente (no versionadas)
│   ├── raw/geodatos/       # capas descargadas por script (no versionadas)
│   └── processed/          # salidas reproducibles que lee el dashboard
├── notebooks/              # Investigación y análisis exploratorio
├── reports/                # Informe ejecutivo
├── docs/                   # Plan, metodología, criterios, diccionario de datos, decisiones
└── tests/                  # Pruebas automáticas
```

## Instalación

Requisitos: [uv](https://docs.astral.sh/uv/) (crea un entorno aislado con Python 3.12, sin usar Conda).

```bash
git clone https://github.com/serugiran96/observatorio_incendios_forestales_2026.git
cd observatorio_incendios_forestales_2026
uv sync                 # crea .venv con Python 3.12 e instala dependencias fijadas en uv.lock
```

Sin uv: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && pip install -e .`

Si tienes Conda activo, ejecuta antes `conda deactivate` para que no interfiera.

**Si el repositorio está en una carpeta sincronizada con iCloud** (por ejemplo, `~/Documents`), iCloud oculta
los archivos de `.venv` y Python deja de encontrar el paquete (`ModuleNotFoundError: observatorio`). Crea
el entorno fuera de la sincronización y enlázalo:

```bash
UV_PROJECT_ENVIRONMENT=venv.nosync uv sync && ln -s venv.nosync .venv
```

Ver `docs/decisiones_tecnicas.md` (DT-09).

## Uso

```bash
uv run pytest                                   # pruebas
uv run python scripts/validar_registro.py       # valida fuentes, evidencias y vacíos de información
```

Flujo completo de datos (cada paso es reproducible y se puede volver a ejecutar):

```bash
# Fase 2 – inventario documental
uv run python scripts/extraer_reportes_emergencia.py --descargar   # reportes OGRD-Congreso
uv run python scripts/indexar_reportes_indeci.py --descargar        # índice y PDF COEN-INDECI
uv run python scripts/extraer_reportes_indeci.py                    # registro e inventario consolidado
# Fase 3 – territorio y teledetección
uv run python scripts/descargar_limites.py                          # 112 distritos con UBIGEO
uv run python scripts/descargar_ecosistemas.py                      # ecosistemas MINAM por distrito
uv run python scripts/agregar_por_distrito.py                       # inventario georreferenciado e indicadores
uv run python scripts/descargar_focos_calor.py                      # requiere FIRMS_MAP_KEY
uv run python scripts/ejecutar_analisis_gee.py                      # requiere GEE_PROJECT y autenticación
```

### Credenciales (no se versionan)

Copia `.env.example` a `.env` y completa:

- `GEE_PROJECT`: ID del proyecto de Google Cloud con Earth Engine habilitado.
- `FIRMS_MAP_KEY`: clave gratuita de [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/).

## Licencia

Código bajo licencia MIT (ver `LICENSE`). Los datos de terceros conservan las licencias de sus
fuentes, indicadas en `data/raw/registro/fuentes.csv`.
