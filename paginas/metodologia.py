"""H. Metodología, fuentes, limitaciones y fecha de actualización."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from observatorio import config, esquemas, tablero

fuentes, evidencias, vacios = tablero.registro_curado()
satelite = tablero.estado_satelital()

st.title("Metodología y fuentes")

archivos = sorted(config.DIR_PROCESSED.glob("*.csv"))
ultima = max((datetime.fromtimestamp(a.stat().st_mtime) for a in archivos), default=None)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Fecha de corte", f"{config.FECHA_CORTE:%d-%m-%Y}", border=True)
c2.metric("Última consulta de fuentes", pd.to_datetime(fuentes["fecha_consulta"]).max().strftime("%d-%m-%Y"),
          border=True)
c3.metric("Datos procesados", f"{ultima:%d-%m-%Y %H:%M}" if ultima else "—", border=True,
          help="Fecha de la última ejecución de los scripts que generan data/processed.")
c4.metric("Análisis satelital", "disponible" if satelite["gee"] else "pendiente", border=True,
          help="Requiere credenciales de Google Earth Engine y NASA FIRMS (ver README).")

st.subheader("Estados de verificación")
st.dataframe(pd.DataFrame({"estado": list(esquemas.ESTADOS_VERIFICACION.values()),
                           "código": list(esquemas.ESTADOS_VERIFICACION)}), hide_index=True)
st.caption("No se concluye que una comunidad no recibió ayuda solo porque no se encontraron registros públicos: "
           "en ese caso el estado es «Atención no verificada» o «Información insuficiente».")

conteo = evidencias.groupby(["categoria", "estado_verificacion"]).size().rename("evidencias").reset_index()
conteo["estado_verificacion"] = conteo["estado_verificacion"].map(esquemas.ESTADOS_VERIFICACION)
with st.expander(f"Evidencias registradas por categoría y estado ({len(evidencias)} en total)"):
    st.dataframe(conteo, hide_index=True)

st.subheader("Fuentes")
tipos = st.multiselect("Tipo de fuente", list(esquemas.TIPOS_FUENTE), format_func=lambda t: esquemas.TIPOS_FUENTE[t],
                       placeholder="Todos")
vista = fuentes[fuentes["tipo_fuente"].isin(tipos)] if tipos else fuentes
st.dataframe(vista[["id_fuente", "institucion", "titulo", "tipo_fuente", "fecha_publicacion", "fecha_consulta",
                    "accesible", "url", "notas"]],
             hide_index=True, height=380,
             column_config={"titulo": st.column_config.TextColumn("Título", width="large"),
                            "url": st.column_config.LinkColumn("Enlace", display_text="abrir"),
                            "notas": st.column_config.TextColumn("Notas y limitaciones", width="large")})
st.caption(f"{len(vista)} de {len(fuentes)} fuentes. «accesible = no» indica que la fuente no respondió o "
           "bloqueó la consulta; la limitación queda registrada.")

st.subheader("Vacíos de información")
st.dataframe(vacios, hide_index=True, column_config={
    "descripcion": st.column_config.TextColumn("Descripción", width="large"),
    "accion_sugerida": st.column_config.TextColumn("Acción sugerida", width="medium")})

st.subheader("Metodología y limitaciones")
for documento, titulo in [("metodologia.md", "Metodología completa"),
                          ("criterios_verificacion.md", "Criterios de verificación"),
                          ("fuentes.md", "Fuentes y su acceso")]:
    ruta = config.DIR_DOCS / documento
    if ruta.exists():
        with st.expander(titulo):
            st.markdown(ruta.read_text(encoding="utf-8"))

st.subheader("Cómo reproducir")
st.code(
    "uv sync\n"
    "uv run python scripts/validar_registro.py\n"
    "uv run python scripts/agregar_por_distrito.py\n"
    "uv run python scripts/construir_matrices.py\n"
    "uv run streamlit run app.py",
    language="bash",
)
st.caption("Código: github.com/serugiran96/observatorio_incendios_forestales_2026 · Datos de terceros con las "
           "licencias de sus fuentes.")
