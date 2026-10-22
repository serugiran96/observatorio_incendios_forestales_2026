# Metodología

Este documento describe cómo se construyen los datos del observatorio. Las fuentes y sus
limitaciones están en [`fuentes.md`](fuentes.md); los criterios de verificación, en
[`criterios_verificacion.md`](criterios_verificacion.md).

## 1. Inventario de incendios (Fase 2)

1. **Reportes COEN-INDECI** (fuente primaria): se indexan desde el feed del portal de emergencias,
   se descargan los PDF y se extraen hechos, ubicación, tabla de daños (EDAN) y acciones de respuesta.
   Los reportes de un mismo incendio se agrupan por lugar y fecha de ocurrencia. Los daños se toman de
   la última actualización y las acciones, de toda la cadena (incluido el anexo de cronología).
2. **Reportes diarios OGRD-Congreso**: se usan para contrastar y para los incendios que no aparecen
   en los reportes COEN indexados (2 casos).
3. **Prensa y notas oficiales**: aportan fallecidos, ayuda anunciada y cifras regionales. Se
   registran con su propio estado de verificación y nunca reemplazan una cifra oficial.
4. **Posibles duplicados**: se marcan cuando dos registros coinciden en provincia, distrito, fechas
   cercanas (≤ 2 días) y nombre de lugar o cifra. No se eliminan; las sumas se informan con y sin ellos.

## 2. Unidad territorial y georreferenciación (Fase 3)

- **Límites:** 112 distritos de Cusco con UBIGEO y población 2018, del servicio de cartografía de
  OSINERGMIN (`scripts/descargar_limites.py`).
- **Asignación:** los nombres de las fuentes se comparan sin tildes ni mayúsculas con la lista
  oficial; las variantes se resuelven solo con alias explícitos (`territorio.ALIAS_OFICIALES`).
  "La Mar" (Calca) se asignó a Lamay por inferencia y se marca como pendiente de verificar.
- **Precisión:** ninguna fuente oficial publica coordenadas de los incendios. El mapa los ubica en un
  punto interior de su distrito y lo indica como aproximado. Las localidades (sectores, comunidades)
  se conservan como texto.
- **Indicadores distritales** (`scripts/agregar_por_distrito.py`): número de incendios, cobertura
  destruida según la EDAN, daños humanos y materiales, ayuda documentada y brechas, en el periodo
  1-sep a 21-oct-2026. Un incendio que abarca varios distritos cuenta en cada uno, pero sus cifras no
  se reparten.

## 3. Ecosistemas

Mapa Nacional de Ecosistemas del Perú (MINAM, 2018), consultado por servicio de mapas solo para
Cusco, con geometría generalizada a unos 50 m (`scripts/descargar_ecosistemas.py`). Se calcula la
superficie de cada ecosistema por distrito en proyección de igual área (ESRI:102033). Esta capa
orienta el módulo de restauración: no se recomiendan intervenciones sin conocer el ecosistema.

## 4. Focos de calor (NASA FIRMS)

- Sensores VIIRS (S-NPP, NOAA-20, NOAA-21; 375 m) y MODIS (1 km), 1-ago a 21-oct-2026.
- La hora UTC se convierte a la hora de Perú (UTC−5). La confianza se unifica en tres niveles: baja,
  nominal y alta.
- **Un foco de calor no es un área quemada.** Se usa solo para **corroborar** los incendios del
  inventario: se cuentan los focos del mismo distrito entre 1 día antes y 3 días después de la fecha
  de ocurrencia. La ausencia de focos no desmiente un incendio: puede deberse a nubes, a un incendio
  breve entre pasos del satélite o a uno de baja intensidad.

## 5. Área quemada y severidad estimadas (Google Earth Engine)

| Paso | Detalle |
|---|---|
| Imágenes | Sentinel-2 SR armonizado; máscara de nubes Cloud Score+ (cs ≥ 0,60) |
| Compuesto previo | Mediana del 1-jul al 15-ago-2026 |
| Compuesto posterior | Mediana del 1-oct al 21-oct-2026 |
| Índices | NDVI = (B8−B4)/(B8+B4); NBR = (B8−B12)/(B8+B12); dNBR = NBR previo − NBR posterior |
| Exclusiones | Agua (JRC, ocurrencia > 50 %), zonas urbanas y nieve/hielo (ESA WorldCover 2021) |
| Cambio candidato | dNBR ≥ 0,10, en grupos de al menos 5 píxeles de 20 m (0,2 ha) |
| Atribución a fuego | Cambio candidato a ≤ 1,5 km de un foco de calor entre los dos compuestos → **área quemada probable**; si no hay foco cercano → **cambio no atribuido** |
| Severidad | Umbrales de Key y Benson (2006): baja 0,10–0,27; moderada-baja 0,27–0,44; moderada-alta 0,44–0,66; alta > 0,66 |
| Erosión | Área quemada probable con pendiente ≥ 30° (Copernicus DEM GLO-30) |
| Referencia | Área quemada MODIS MCD64A1 (500 m), cuando esté publicada |

### Limitaciones del análisis satelital

- **Sin validación de campo.** Los umbrales de dNBR se calibraron en bosques de Norteamérica; en
  pajonales altoandinos la señal es más débil y se recupera rápido con las primeras lluvias. Por eso
  se habla de **severidad estimada**.
- **Ventanas de temporada.** Los incendios de fines de julio y agosto pueden quedar dentro del
  compuesto previo y subestimarse. En octubre aumenta la nubosidad, sobre todo en La Convención.
- **Atribución.** Las quemas agrícolas generan focos de calor y pérdida de vegetación, y no se
  distinguen automáticamente de los incendios forestales. Las cosechas o la sequía pueden reducir el
  NBR sin fuego (se informan como "cambio no atribuido").
- **MODIS MCD64A1** se publica con 1–2 meses de retraso y, con 500 m, no detecta incendios pequeños.
- **EDAN frente a satélite.** La "cobertura natural destruida" de la EDAN es una estimación de campo
  hecha por las municipalidades, no un área medida. Las diferencias con el satélite son esperables y
  se muestran, no se corrigen.

## 6. Atención inmediata (0–90 días)

`scripts/construir_matrices.py` arma una matriz con una fila por incendio del periodo prioritario,
a partir del inventario, las acciones de respuesta reportadas al COEN y las evidencias manuales del
mismo distrito. Los criterios y estados están en [`criterios_verificacion.md`](criterios_verificacion.md).
No se calcula ningún puntaje.

## 7. Restauración (3 meses – 5 años)

- Catálogo curado de 11 medidas (`data/raw/registro/medidas_restauracion.csv`), cada una con su
  sustento y fuentes: lineamientos y opciones de restauración de SERFOR, el estudio del IGP sobre
  pastizales quemados en Calca y Quispicanchi (recuperación de la biomasa en hasta cuatro años),
  estudios sobre rebrote en pajonales y bosques montanos, y guías de control de erosión post-incendio.
- **Nivel de sustento explícito:** justificada, condicionada a evaluación de campo o satélite,
  hipótesis o no recomendada. Plantar especies exóticas o plantar en pajonales y bofedales no se
  recomienda.
- **Aplicación por distrito:** según los ecosistemas presentes (≥ 10 ha) y los daños documentados.
  Como no se sabe qué ecosistema se quemó, las medidas condicionadas e hipotéticas quedan como
  "verificar en campo". El control de erosión espera el área quemada con pendiente ≥ 30° del
  análisis satelital.

## 8. Presupuesto y brechas

- Las líneas humanitarias y productivas son por incendio y usan las cantidades de la EDAN
  (damnificados, viviendas, lesionados, hectáreas de cultivo, cabezas de ganado). Las ecológicas son
  por distrito.
- **Costos:** ninguno tiene fuente al 21-oct-2026; todas las líneas figuran como "pendiente de
  cotización", con el método de estimación. El validador rechaza un costo sin fuente.
- **Brecha:** se calcula solo con costo total y recursos documentados en soles; si no, se explica
  por qué no es calculable. Los presupuestos regionales documentados (proyecto CUI 2526543,
  PP 0068) se muestran aparte y no se descuentan de ninguna línea.
- **Escenarios:** el dashboard permite escribir costos unitarios supuestos para explorar órdenes de
  magnitud. Se rotulan como supuestos de quien consulta y no se guardan.

## 9. Dashboard

`app.py` (Streamlit, Plotly, Folium) solo lee `data/processed` y el registro curado. Paneles: A
resumen ejecutivo, B mapa, C filtros globales (barra lateral), D ficha territorial, E atención
inmediata, F restauración, G presupuesto y escenarios, H metodología y fuentes. Cada gráfico tiene
su tabla equivalente. Las capas satelitales aparecen solo si existen sus archivos.

