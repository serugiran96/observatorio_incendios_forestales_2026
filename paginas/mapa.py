"""B. Mapa interactivo por capas."""

from __future__ import annotations

import html

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from observatorio import config, indicadores, tablero
from observatorio.tablero import fmt

f = tablero.filtros()
inv = tablero.aplicar(tablero.inventario(), f)
distritos = tablero.leer_geo("limites_cusco_distritos.geojson")
provincias = tablero.leer_geo("limites_cusco_provincias.geojson")
colores = tablero.paleta()
satelite = tablero.estado_satelital()

st.title("Mapa")
st.caption(f.describir())

INDICADORES = {
    "n_incendios": ("Número de incendios", 0),
    "cobertura_natural_destruida_ha": ("Cobertura natural destruida (ha, EDAN)", 1),
    "pct_area": ("Cobertura destruida (% de la superficie del distrito)", 2),
    "personas_damnificadas": ("Personas damnificadas", 0),
}
izquierda, derecha = st.columns([2, 1])
capa = izquierda.radio("Capa temática", ["Indicador de incendios", "Ecosistemas (MINAM)"], horizontal=True)
indicador = derecha.selectbox("Indicador", list(INDICADORES), format_func=lambda k: INDICADORES[k][0],
                              disabled=capa != "Indicador de incendios")

datos = distritos.merge(indicadores.agregar_por_ubigeo(inv), on="ubigeo", how="left")
for col in ["n_incendios", *indicadores.CIFRAS]:
    datos[col] = datos[col].fillna(0)
datos["pct_area"] = datos["cobertura_natural_destruida_ha"] / (datos["area_km2"] * 100) * 100
etiqueta, decimales = INDICADORES[indicador]
datos["valor_texto"] = datos[indicador].map(lambda v: fmt(v, decimales))

mapa = folium.Map(location=[-13.6, -72.0], zoom_start=7, tiles=None, control_scale=True)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, HERE, Garmin, © OpenStreetMap", name="Fondo gris (Esri)", max_zoom=16,
).add_to(mapa)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(mapa)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, Maxar, Earthstar Geographics", name="Imagen satelital de fondo (Esri)", show=False,
).add_to(mapa)

leyenda = []
if capa == "Indicador de incendios":
    # Clases por quintiles de los distritos con valor > 0; intervalos (inferior, superior]
    positivos = datos.loc[datos[indicador] > 0, indicador]
    cuantiles = np.quantile(positivos, [0.2, 0.4, 0.6, 0.8, 1]) if len(positivos) else [1]
    cortes = np.unique(np.concatenate([[0], cuantiles]))
    rampa = colores["secuencial"][1:]
    tonos = [rampa[int(round(i))] for i in np.linspace(0, len(rampa) - 1, len(cortes) - 1)]

    def color_de(valor: float) -> str | None:
        if valor <= 0:
            return None
        return tonos[min(int(np.searchsorted(cortes[1:-1], valor, side="left")), len(tonos) - 1)]

    datos["color"] = datos[indicador].map(color_de)
    folium.GeoJson(
        datos[["ubigeo", "distrito", "provincia", "valor_texto", "n_incendios", "color", "geometry"]].to_json(),
        name=etiqueta,
        style_function=lambda ft: {
            "fillColor": ft["properties"]["color"] or "#ffffff",
            "fillOpacity": 0.75 if ft["properties"]["color"] else 0.05,
            "color": "#898781", "weight": 0.6,
        },
        highlight_function=lambda ft: {"weight": 2, "color": "#0b0b0b"},
        tooltip=folium.GeoJsonTooltip(fields=["distrito", "provincia", "valor_texto"],
                                      aliases=["Distrito", "Provincia", etiqueta]),
    ).add_to(mapa)
    for i, tono in enumerate(tonos):
        leyenda.append((tono, f"más de {fmt(cortes[i], decimales)} hasta {fmt(cortes[i + 1], decimales)}"))
    leyenda.append(("#ffffff", "sin registro"))
else:
    eco = tablero.ecosistemas_agrupados()
    orden = {"Bofedal": 0, "Pajonal": 1, "Bosque nativo": 2}
    for fila in eco.itertuples():
        color = colores["categorica"][orden[fila.grupo]]
        folium.GeoJson(
            fila.geometry.__geo_interface__, name=f"Ecosistema: {fila.grupo}",
            style_function=lambda ft, c=color: {"fillColor": c, "fillOpacity": 0.6, "color": c, "weight": 0.3},
            tooltip=fila.grupo,
        ).add_to(mapa)
        leyenda.append((color, fila.grupo))
    folium.GeoJson(distritos[["distrito", "geometry"]].to_json(), name="Distritos",
                   style_function=lambda ft: {"fillOpacity": 0, "color": "#898781", "weight": 0.5},
                   tooltip=folium.GeoJsonTooltip(fields=["distrito"], aliases=["Distrito"])).add_to(mapa)

folium.GeoJson(provincias.to_json(), name="Provincias",
               style_function=lambda ft: {"fillOpacity": 0, "color": "#52514e", "weight": 1.6}).add_to(mapa)

# Un símbolo por distrito, en su punto interior (ninguna fuente publica la ubicación del incendio)
capa_incendios = folium.FeatureGroup(name="Incendios por distrito (punto aproximado)", show=True).add_to(mapa)
for ubigeo, grupo in inv.dropna(subset=["latitud_aprox"]).groupby(inv["ubigeo"].astype(str).str.split("|").str[0]):
    abiertos = int(grupo["estado"].eq("abierto al último reporte").sum())
    primero = grupo.iloc[0]
    lineas = []
    for fila in grupo.sort_values("fecha_ocurrencia", ascending=False).itertuples():
        partes = [f"{fila.fecha_ocurrencia:%d-%m-%Y}"]
        if isinstance(fila.localidad, str):
            partes.append(html.escape(fila.localidad))
        partes.append(html.escape(str(fila.estado)))
        if pd.notna(fila.cobertura_natural_destruida_ha):
            partes.append(f"{fmt(fila.cobertura_natural_destruida_ha, 1)} ha")
        if pd.notna(fila.personas_damnificadas):
            partes.append(f"{fmt(fila.personas_damnificadas)} damnificados")
        lineas.append(" · ".join(partes))
    contenido = (f"<b>{html.escape(str(primero.distrito))}</b> ({html.escape(str(primero.provincia))})<br>"
                 f"{len(grupo)} incendio(s), {abiertos} abierto(s) al último reporte<br><br>"
                 + "<br>".join(lineas[:12]) + ("<br>…" if len(lineas) > 12 else "")
                 + "<br><br><i>Punto aproximado: interior del distrito</i>")
    folium.CircleMarker(
        [primero.latitud_aprox, primero.longitud_aprox], radius=4 + 3 * np.sqrt(len(grupo)), weight=2,
        color="#ffffff", fill=True, fill_opacity=0.95,
        fill_color=colores["categorica"][1] if abiertos else colores["tinta_secundaria"],
        tooltip=f"{primero.distrito}: {len(grupo)} incendio(s)",
        popup=folium.Popup(contenido, max_width=360),
    ).add_to(capa_incendios)

# Capas satelitales: solo si el análisis se ejecutó (requiere credenciales)
if satelite["focos"]:
    focos = tablero.leer_procesado("focos_calor_cusco.csv")
    focos = focos[(pd.to_datetime(focos["fecha_local"]) >= pd.Timestamp(f.inicio))
                  & (pd.to_datetime(focos["fecha_local"]) <= pd.Timestamp(f.fin))]
    capa_focos = folium.FeatureGroup(name="Focos de calor FIRMS (no son área quemada)", show=False).add_to(mapa)
    for foco in focos.itertuples():
        folium.CircleMarker([foco.latitud, foco.longitud], radius=2, color=colores["categorica"][4],
                            fill=True, weight=0, fill_opacity=0.8).add_to(capa_focos)
meta = satelite["gee_metadatos"]
if meta:
    limites = meta["limites_imagenes"]
    for archivo, nombre in [("dnbr_cusco.png", "dNBR Sentinel-2 (severidad estimada)"),
                            ("quemado_probable_cusco.png", "Área quemada probable (Sentinel-2 + focos)")]:
        ruta = config.DIR_PROCESSED / "mapas" / archivo
        if ruta.exists():
            folium.raster_layers.ImageOverlay(
                str(ruta), bounds=[[limites["sur"], limites["oeste"]], [limites["norte"], limites["este"]]],
                name=nombre, opacity=0.7, show=False).add_to(mapa)

oeste, sur, este, norte = distritos.total_bounds
mapa.fit_bounds([[sur, oeste], [norte, este]])
folium.LayerControl(collapsed=True).add_to(mapa)
st_folium(mapa, height=620, use_container_width=True, returned_objects=[])

# Leyenda (fuera del mapa para que sea legible y accesible)
muestras = " ".join(
    f"<span style='display:inline-flex;align-items:center;margin-right:14px'>"
    f"<span style='width:14px;height:14px;border-radius:3px;margin-right:6px;background:{c};"
    f"border:1px solid #c3c2b7'></span>{html.escape(t)}</span>" for c, t in leyenda)
st.markdown(f"**{etiqueta if capa == 'Indicador de incendios' else 'Ecosistemas'}**<br>{muestras}",
            unsafe_allow_html=True)
st.markdown(
    f"<span style='display:inline-flex;align-items:center;margin-right:14px'><span style='width:12px;height:12px;"
    f"border-radius:50%;margin-right:6px;background:{colores['categorica'][1]}'></span>Distrito con algún incendio abierto al último reporte</span>"
    f"<span style='display:inline-flex;align-items:center'><span style='width:12px;height:12px;border-radius:50%;"
    f"margin-right:6px;background:{colores['tinta_secundaria']}'></span>Todos cerrados, en cierre temporal o sin seguimiento · tamaño según el número de incendios</span>",
    unsafe_allow_html=True,
)
st.caption(
    "Ninguna fuente oficial publica coordenadas de los incendios: cada punto está en el interior de su distrito. "
    "Límites: OSINERGMIN/INEI. Ecosistemas: MINAM (2018), solo bofedal, pajonal y bosque nativo. "
    + ("Capas satelitales disponibles en el control de capas." if meta or satelite["focos"]
       else "Capas satelitales: pendientes (requieren credenciales de Earth Engine y NASA FIRMS).")
)

if capa == "Indicador de incendios":
    tabla = datos[datos[indicador] > 0].sort_values(indicador, ascending=False)[
        ["provincia", "distrito", "ubigeo", "n_incendios", "cobertura_natural_destruida_ha", "pct_area",
         "personas_damnificadas"]]
    tablero.ver_tabla(tabla, "Ver la tabla del mapa")
