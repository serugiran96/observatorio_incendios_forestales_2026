"""G. Presupuesto, brechas y escenarios."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from observatorio import presupuesto, restauracion, tablero
from observatorio.tablero import fmt

f = tablero.filtros()
lineas = tablero.leer_procesado("matriz_presupuesto.csv", dtype={"ubigeo": str, "id_evento": str})
contexto = tablero.leer_procesado("recursos_documentados_contexto.csv")
costos = presupuesto.cargar_costos()
fuentes, _, _ = tablero.registro_curado()

st.title("Presupuesto y brechas")
st.error(
    "**No se inventan presupuestos.** Ningún costo unitario tiene todavía una fuente verificable, así que todas "
    "las líneas figuran como *pendientes de cotización* y los totales no se calculan. Las cantidades sí provienen "
    "de la EDAN o se marcan como pendientes.",
    icon=":material/request_quote:",
)

if f.provincias:
    lineas = lineas[lineas["provincia"].isin(f.provincias)]
if f.distritos:
    lineas = lineas[lineas["ubigeo"].astype(str).str.split("|").apply(lambda us: bool(set(us) & set(f.distritos)))]

componentes = st.multiselect("Componente", list(restauracion.COMPONENTES),
                             default=["humanitaria", "rehabilitacion_productiva", "restauracion_ecologica", "monitoreo"],
                             format_func=restauracion.COMPONENTES.get, placeholder="Ninguno")
lineas = lineas[lineas["componente"].isin(componentes)]

resumen = lineas.groupby(["componente", "id_intervencion", "intervencion", "unidad"], as_index=False).agg(
    lineas=("id_linea", "count"), territorios=("ubigeo", "nunique"),
    cantidad=("cantidad", "sum"), sin_cantidad=("cantidad", lambda s: int(s.isna().sum())),
    estado_costo=("estado_costo", "first"))
resumen["componente"] = resumen["componente"].map(restauracion.COMPONENTES)
st.subheader("Resumen por intervención")
st.dataframe(resumen, hide_index=True, column_config={
    "intervencion": st.column_config.TextColumn("Intervención", width="large"),
    "territorios": "Distritos", "cantidad": st.column_config.NumberColumn("Cantidad documentada", format="localized"),
    "sin_cantidad": "Líneas sin cantidad", "estado_costo": "Costo"})
st.caption("La cantidad de «Regeneración natural» es la cobertura destruida según la EDAN: una referencia, no el área "
           "a intervenir. Control de erosión y bosques necesitan el área quemada medida por satélite.")

st.subheader("Matriz de intervenciones")
vista = lineas.assign(componente=lineas["componente"].map(restauracion.COMPONENTES),
                      localidad=lineas["localidad"].fillna(""))
st.dataframe(vista[[
    "id_linea", "componente", "intervencion", "provincia", "distrito", "localidad", "problema", "beneficiarios",
    "cantidad", "unidad", "fuente_cantidad", "estado_costo", "costo_total_soles", "recursos_documentados",
    "donaciones_o_anuncios", "brecha", "entidades_competentes", "como_estimar"]],
    hide_index=True, height=420,
    column_config={
        "intervencion": st.column_config.TextColumn("Intervención", width="medium"),
        "problema": st.column_config.TextColumn("Problema", width="medium"),
        "cantidad": st.column_config.NumberColumn("Cantidad", format="localized"),
        "costo_total_soles": st.column_config.NumberColumn("Costo total (S/)", format="localized"),
        "recursos_documentados": st.column_config.TextColumn("Recursos documentados", width="medium"),
        "donaciones_o_anuncios": st.column_config.TextColumn("Donaciones o anuncios", width="medium"),
        "entidades_competentes": st.column_config.TextColumn("Entidades competentes (referencial)", width="medium"),
        "como_estimar": st.column_config.TextColumn("Cómo estimar el costo", width="large"),
    })
st.download_button("Descargar la matriz (CSV)", lineas.to_csv(index=False), file_name="matriz_presupuesto.csv",
                   mime="text/csv", icon=":material/download:")
st.caption("Las competencias son referenciales: según el nivel de emergencia, el gobierno local conduce la atención "
           "y distribuye bienes de ayuda humanitaria (niveles 1-2), el Gobierno Regional en el nivel 3, e INDECI "
           "provee bienes según requerimiento (fuente F-0029).")

st.subheader("Recursos documentados que no se pueden asignar a una línea")
contexto = contexto.assign(estado_verificacion=contexto["estado_verificacion"].map(tablero.ETIQUETAS_ATENCION))
st.dataframe(contexto.merge(fuentes[["id_fuente", "institucion", "url"]], on="id_fuente", how="left"),
             hide_index=True, column_config={
                 "descripcion": st.column_config.TextColumn("Recurso", width="large"),
                 "monto_soles": st.column_config.NumberColumn("Monto (S/)", format="localized"),
                 "estado_verificacion": "Estado de verificación", "institucion": "Fuente",
                 "url": st.column_config.LinkColumn("Enlace", display_text="abrir")})
st.caption("Son presupuestos regionales de prevención y respuesta (no de esta temporada en particular). No se "
           "descuentan de ninguna línea.")

st.subheader("Escenarios con costos supuestos")
st.markdown(
    "Escriba un costo unitario para explorar órdenes de magnitud. **Es un supuesto suyo, no una cotización ni un "
    "presupuesto oficial**: el resultado no se guarda y no se muestra en otras páginas."
)
editable = costos[costos["id_intervencion"].isin(lineas["id_intervencion"].unique())][
    ["id_intervencion", "intervencion", "unidad", "como_estimar"]].assign(costo_supuesto_soles=None)
editado = st.data_editor(
    editable, hide_index=True, disabled=["id_intervencion", "intervencion", "unidad", "como_estimar"],
    column_config={"costo_supuesto_soles": st.column_config.NumberColumn("Costo unitario supuesto (S/)", min_value=0),
                   "como_estimar": st.column_config.TextColumn("Cómo estimarlo", width="large")},
    key="escenario_costos")
supuestos = {r.id_intervencion: float(r.costo_supuesto_soles) for r in editado.itertuples()
             if pd.notna(r.costo_supuesto_soles)}
if supuestos:
    escenario = presupuesto.escenario(lineas, supuestos)
    escenario = escenario[escenario["id_intervencion"].isin(supuestos)]
    total = escenario["total_escenario_soles"].sum()
    st.metric("Total del escenario (supuesto)", f"S/ {fmt(total)}", border=True,
              help="Cantidad documentada × costo supuesto. Excluye líneas sin cantidad.")
    st.dataframe(escenario.assign(componente=escenario["componente"].map(restauracion.COMPONENTES)), hide_index=True,
                 column_config={"total_escenario_soles": st.column_config.NumberColumn("Total supuesto (S/)",
                                                                                       format="localized"),
                                "costo_unitario_supuesto": st.column_config.NumberColumn("Costo supuesto (S/)",
                                                                                         format="localized")})
    sin_cantidad = int(escenario["lineas_sin_cantidad"].sum())
    if sin_cantidad:
        st.caption(f"{sin_cantidad} líneas sin cantidad no entran en el total.")
