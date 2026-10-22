"""E. Atención inmediata (0–90 días): matriz por incendio con criterios explícitos, sin ranking."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from observatorio import atencion, tablero
from observatorio.tablero import fmt

f = tablero.filtros()
matriz = tablero.aplicar(tablero.matriz_atencion(), f, columna_estado="estado_evento")
fuentes, evidencias, _ = tablero.registro_curado()

st.title("Atención inmediata")
st.caption(f"Incendios del periodo prioritario (1-sep a 21-oct-2026) · {f.describir()}")
st.warning(
    "**Esto no es un ranking de abandono.** Cada incendio muestra qué criterios cumple y por qué. "
    "«Atención no verificada» significa que no se encontró registro público de la atención, "
    "no que la población no haya sido atendida.",
    icon=":material/balance:",
)

with st.expander("Criterios usados (transparentes y verificables)"):
    st.dataframe(
        pd.DataFrame([{"criterio": e, "grupo": g} for e, g in atencion.CRITERIOS.values()]),
        hide_index=True,
    )
    st.markdown(
        "- **Seguimiento humanitario:** el reporte oficial registra daños a personas, viviendas o medios de vida.\n"
        "- **Verificar atención:** la información pública no permite confirmar si la atención llegó o está "
        "desactualizada. Se recomienda consultar a la municipalidad distrital y al COER Cusco.\n"
        f"- El umbral de desactualización es de {atencion.UMBRAL_DIAS_SIN_ACTUALIZACION} días entre el último "
        "reporte y la fecha de corte."
    )

conteo = matriz["estado_atencion"].value_counts()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Incendios en la matriz", fmt(len(matriz)), border=True)
c2.metric("Con seguimiento humanitario", fmt(matriz["seguimiento_humanitario"].sum()), border=True)
c3.metric("Atención documentada", fmt(conteo.get("atencion_documentada", 0)), border=True)
c4.metric("Atención no verificada", fmt(conteo.get("atencion_no_verificada", 0)), border=True)

izquierda, derecha = st.columns(2)
grupo = izquierda.segmented_control(
    "Mostrar", ["Seguimiento humanitario o verificar atención", "Seguimiento humanitario", "Verificar atención",
                "Todos"], default="Seguimiento humanitario o verificar atención")
criterios = derecha.multiselect("Que cumplan alguno de estos criterios", list(atencion.CRITERIOS),
                                format_func=lambda k: atencion.CRITERIOS[k][0],
                                placeholder="Cualquiera")
vista = matriz
if grupo == "Seguimiento humanitario o verificar atención":
    vista = vista[vista["seguimiento_humanitario"] | vista["verificar_atencion"]]
elif grupo == "Seguimiento humanitario":
    vista = vista[vista["seguimiento_humanitario"]]
elif grupo == "Verificar atención":
    vista = vista[vista["verificar_atencion"]]
if criterios:
    vista = vista[vista[criterios].any(axis=1)]

vista = vista.assign(atencion=vista["estado_atencion"].map(tablero.ETIQUETAS_ATENCION),
                     danos_estado=vista["estado_danos"].map(tablero.ETIQUETAS_ATENCION))
columnas = {
    "provincia": "Provincia",
    "distrito_oficial": "Distrito",
    "localidad": "Comunidad / localidad",
    "fecha_ocurrencia": st.column_config.DateColumn("Fecha del incendio", format="DD/MM/YYYY"),
    "atencion": "Verificación de la atención",
    "motivos": st.column_config.TextColumn("Criterios que cumple", width="large"),
    "estado_evento": "Estado del incendio",
    "danos": st.column_config.TextColumn("Daños", width="medium"),
    "personas_y_medios_de_vida": st.column_config.TextColumn("Personas y medios de vida", width="medium"),
    "necesidades_documentadas": st.column_config.TextColumn("Necesidades documentadas", width="medium"),
    "ayuda_anunciada": st.column_config.TextColumn("Ayuda anunciada", width="medium"),
    "ayuda_entregada_con_evidencia": st.column_config.TextColumn("Ayuda entregada con evidencia", width="large"),
    "necesidades_pendientes": st.column_config.TextColumn("Necesidades pendientes", width="medium"),
    "instituciones": st.column_config.TextColumn("Instituciones", width="medium"),
    "ultima_actualizacion": "Última actualización",
    "fuentes": "Fuentes",
    "danos_estado": "Verificación del daño",
}
if "focos_calor_en_ventana" in vista.columns:
    columnas["focos_calor_en_ventana"] = st.column_config.NumberColumn(
        "Focos de calor (−1/+3 días)", help="Solo corrobora; la ausencia de focos no desmiente el incendio.")
st.dataframe(vista[list(columnas)], hide_index=True, column_config=columnas, height=520)
st.caption(f"{len(vista)} incendios mostrados. Fuentes: reportes COEN-INDECI y OGRD-Congreso; anuncios y "
           "entregas de prensa y notas oficiales registradas en evidencias.csv.")
st.download_button("Descargar la matriz (CSV)", vista.drop(columns=["atencion", "danos_estado"]).to_csv(index=False),
                   file_name="matriz_atencion_inmediata.csv", mime="text/csv", icon=":material/download:")

st.subheader("Ayuda sin territorio identificado")
regional = atencion.ayuda_regional(evidencias)
if regional.empty:
    st.caption("No hay anuncios regionales registrados.")
else:
    regional = regional.assign(estado=regional["estado_verificacion"].map(tablero.ETIQUETAS_ATENCION))
    st.dataframe(regional[["descripcion", "estado", "institucion", "fecha_publicacion", "url"]], hide_index=True,
                 column_config={"descripcion": st.column_config.TextColumn("Anuncio o entrega", width="large"),
                                "estado": "Estado", "institucion": "Fuente", "fecha_publicacion": "Publicado",
                                "url": st.column_config.LinkColumn("Enlace", display_text="abrir")})
    st.caption("Anuncios sin provincia o distrito: no se atribuyen a ningún incendio.")
