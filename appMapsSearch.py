# app.py
# Streamlit app: Mapa -> elegir ubicación -> generar modelo 3D y gráficas + GLB urbano OSM + Mapbox
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import folium
from streamlit_folium import st_folium
from io import BytesIO
from datetime import date
import pandas as pd
import requests
import plotly.graph_objects as go
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import trimesh
import buildings3d

# ─────────────────────────────────────────────
# CONFIGURACIÓN Y ESTADO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Bioclima 3D", layout="wide")
st.title("Diseño Bioclimático: Mapa → Modelo 3D → Gráficas + GLB urbano")

MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

if "busy" not in st.session_state:
    st.session_state.busy = False
if "center" not in st.session_state:
    st.session_state.center = [19.4326, -99.1332]  # CDMX por defecto
BUSY = st.session_state.busy

# ─────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────
def series_dummy(n=12, lat=0.0):
    m = np.arange(n)
    k = np.clip(abs(lat)/90.0, 0, 1)
    tmax = 30 + (6+4*k)*np.sin(2*np.pi*(m-2)/n)
    tmin = 15 + (5+2*k)*np.sin(2*np.pi*(m-3)/n)
    viento = 4 + (1.2+0.6*k)*np.sin(2*np.pi*(m+1)/n)
    radiacion = 180 + (50+30*k)*np.sin(2*np.pi*(m-2)/n)
    return tmax, tmin, viento, radiacion

def alturas_conceptuales(tmax, viento, radiacion=None):
    rad = np.zeros_like(tmax) if radiacion is None else radiacion
    h = tmax + 0.5*viento + 0.1*rad
    max_h = np.max(h) if np.any(np.isfinite(h)) else 1.0
    return (h / max_h) * 100.0

def plot_modelo_3d(alturas, elev=25, azim=210, paso=5.0, escala=0.15, torre_xy=1.0):
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111, projection="3d")
    for i, h in enumerate(alturas):
        x = np.array([-torre_xy, -torre_xy, torre_xy, torre_xy])
        y = np.array([-torre_xy, torre_xy, torre_xy, -torre_xy])
        z_base = i * paso
        z_top = z_base + h * escala
        base = list(zip(x, y, [z_base]*4))
        top = list(zip(x, y, [z_top]*4))
        caras = [base, top]
        poly = Poly3DCollection(caras, facecolor=cm.viridis(i / max(1, len(alturas)-1)), alpha=0.85)
        ax.add_collection3d(poly)
        ax.text(torre_xy*1.2, torre_xy*1.2, z_base, MESES[i % 12], fontsize=8)
    ax.set_title("Modelo Paramétrico Bioclimático")
    ax.set_xlabel("Eje X"); ax.set_ylabel("Eje Y"); ax.set_zlabel("Altura (conceptual)")
    ax.view_init(elev=elev, azim=azim)
    ax.set_zlim(0, len(alturas)*paso + 30)
    plt.tight_layout()
    return fig

def line_chart(values, title, ylabel):
    fig = plt.figure(figsize=(4, 3))
    plt.plot(range(1, len(values)+1), values, marker="o")
    plt.title(title)
    plt.xlabel("Mes"); plt.ylabel(ylabel)
    plt.xticks(range(1, 13), MESES)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig

def requests_retry_session(retries=3, backoff_factor=2.0):
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff_factor, status_forcelist=(429,500,502,503,504))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def fetch_open_meteo_monthly(lat, lon, year=None):
    if year is None:
        year = date.today().year - 1
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
        "daily": ["temperature_2m_max", "temperature_2m_min", "wind_speed_10m_max", "shortwave_radiation_sum"],
        "timezone": "auto"
    }
    base = "https://archive-api.open-meteo.com/v1/era5"
    resp = requests_retry_session().get(base, params=params, timeout=60)
    data = resp.json()
    df = pd.DataFrame({
        "date": pd.to_datetime(data["daily"]["time"]),
        "tmax": data["daily"]["temperature_2m_max"],
        "tmin": data["daily"]["temperature_2m_min"],
        "viento": data["daily"]["wind_speed_10m_max"],
        "rad": data["daily"]["shortwave_radiation_sum"]
    }).set_index("date")
    m = df.resample("MS").mean().iloc[:12]
    return m["tmax"].to_numpy(), m["tmin"].to_numpy(), m["viento"].to_numpy(), m["rad"].to_numpy()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("Entrada de datos")
    uploaded = st.file_uploader("CSV (tmax,tmin,viento[,radiacion])", type=["csv"], disabled=BUSY)
    elev = st.slider("Elevación cámara (3D)", 0, 85, 25)
    azim = st.slider("Azimut cámara (3D)", 0, 360, 210)
    usar_openmeteo = st.checkbox("Usar datos reales (Open-Meteo ERA5)", True)
    anio = st.number_input("Año histórico", 1979, 2100, date.today().year - 1)
    radio = st.slider("Radio de búsqueda OSM (m)", 200, 2000, 600, step=50)
    paso = st.slider("Separación entre torres", 2, 20, 5)
    escala = st.slider("Escala de altura", 0.05, 0.5, 0.15)
    base = st.slider("Tamaño base de la torre", 1, 5, 1)

# ─────────────────────────────────────────────
# MAPA INTERACTIVO CON MAPBOX Y OTRAS CAPAS
# ─────────────────────────────────────────────
st.subheader("1) Buscar o elegir ubicación")

col_map, col_search = st.columns([3, 2])
with col_search:
    query = st.text_input("🔍 Buscar lugar (ej: Puebla, México)")
    buscar = st.button("Buscar")
    if buscar and query.strip():
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": query, "format": "json", "limit": 1}
            resp = requests.get(url, params=params, timeout=10, headers={"User-Agent": "streamlit-app"})
            if resp.status_code != 200 or "application/json" not in resp.headers.get("Content-Type", ""):
                raise ValueError("Respuesta inválida del servidor")
            data = resp.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                st.session_state.center = [lat, lon]
                st.success(f"Ubicación encontrada: {data[0]['display_name']}")
            else:
                st.warning("No se encontró esa ubicación.")
        except Exception as e:
            st.warning(f"No se pudo buscar la ubicación: {e}")

# Token de Mapbox
MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN", "") or st.text_input(
    "🔑 Token de Mapbox (desde account.mapbox.com):", type="password"
)

map_styles = {
    "OpenStreetMap": None,
    "Satelital (Esri)": "esri",
    "Terreno (Stamen)": "stamen-terrain",
    "Carto Light": "carto-light",
    "Mapbox Streets": "mapbox/streets-v12",
    "Mapbox Satellite": "mapbox/satellite-v9",
    "Mapbox Outdoors": "mapbox/outdoors-v12",
    "Mapbox Light": "mapbox/light-v11",
    "Mapbox Dark": "mapbox/dark-v11"
}

tipo_mapa = st.selectbox("Tipo de mapa", list(map_styles.keys()))

center = st.session_state.center
m = folium.Map(location=center, zoom_start=12, control_scale=True)
style = map_styles[tipo_mapa]

if tipo_mapa == "OpenStreetMap":
    folium.TileLayer("OpenStreetMap", attr="© OpenStreetMap contributors").add_to(m)

elif tipo_mapa == "Satelital (Esri)":
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        name="Esri Satellite",
        attr="Tiles © Esri — Earthstar Geographics, CNES/Airbus DS, USGS",
        overlay=False
    ).add_to(m)

elif tipo_mapa == "Terreno (Stamen)":
    folium.TileLayer(
        "Stamen Terrain",
        attr="Map tiles by Stamen Design — Map data © OpenStreetMap contributors"
    ).add_to(m)

elif tipo_mapa == "Carto Light":
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        name="Carto Light",
        attr="© OpenStreetMap contributors, © CARTO",
        overlay=False
    ).add_to(m)

elif style and style.startswith("mapbox"):
    if not MAPBOX_TOKEN:
        st.warning("⚠️ Ingresa tu token de Mapbox para usar estos estilos.")
    else:
        folium.TileLayer(
            tiles=f"https://api.mapbox.com/styles/v1/{style}/tiles/256/{{z}}/{{x}}/{{y}}@2x?access_token={MAPBOX_TOKEN}",
            attr='© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> © OpenStreetMap contributors',
            name=tipo_mapa,
            overlay=False
        ).add_to(m)

folium.LatLngPopup().add_to(m)
map_data = st_folium(m, height=500, width=None)

# Actualizar coordenadas si se hace click
if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
    st.session_state.center = [
        map_data["last_clicked"]["lat"],
        map_data["last_clicked"]["lng"]
    ]

lat, lon = st.session_state.center

col1, col2, col3 = st.columns(3)
run = col1.button("Diseño Bioclimático", type="primary", use_container_width=True)
gen_glb = col2.button("Modelo 3D urbano (GLB)", use_container_width=True)
view_glb = col3.button("Ver modelo 3D urbano", use_container_width=True)

st.divider()

# ─────────────────────────────────────────────
# DISEÑO BIOCLIMÁTICO
# ─────────────────────────────────────────────
if run:
    with st.spinner("Generando diseño bioclimático..."):
        try:
            if usar_openmeteo:
                tmax, tmin, viento, radiacion = fetch_open_meteo_monthly(lat, lon, int(anio))
            else:
                tmax, tmin, viento, radiacion = series_dummy(12, lat)
            alturas = alturas_conceptuales(tmax, viento, radiacion)
            fig3d = plot_modelo_3d(alturas, elev=elev, azim=azim, paso=paso, escala=escala, torre_xy=base)
            st.pyplot(fig3d)
            col_a, col_b = st.columns(2)
            with col_a:
                st.pyplot(line_chart(tmax, "Temperatura Máxima", "°C"))
                st.pyplot(line_chart(viento, "Viento", "m/s"))
            with col_b:
                st.pyplot(line_chart(radiacion, "Radiación", "W/m²"))
                st.pyplot(line_chart(alturas, "Alturas Conceptuales", "%"))
            buf = BytesIO()
            fig3d.savefig(buf, format="png", dpi=200)
            st.download_button("Descargar 3D como PNG", buf.getvalue(), "bioclima_3d.png", "image/png")
        except Exception as e:
            st.error(f"Error generando diseño: {e}")

# ─────────────────────────────────────────────
# MODELO URBANO OSM
# ─────────────────────────────────────────────
if gen_glb:
    with st.spinner("Descargando edificios OSM y generando GLB..."):
        try:
            cfg = buildings3d.OSM3DConfig(lat=float(lat), lon=float(lon), radius_m=float(radio))
            path = buildings3d.build_glb_from_osm(cfg, "osm_buildings.glb")
            with open(path, "rb") as f:
                st.download_button("Descargar modelo urbano (.glb)", f, "osm_buildings.glb", "model/gltf-binary")
            st.success("Modelo urbano generado ✅")
        except Exception as e:
            st.error(f"Error generando modelo urbano: {e}")

if view_glb:
    try:
        glb_path = "osm_buildings.glb"
        scene_or_mesh = trimesh.load(glb_path, force="scene")
        vertices_all, i, j, k = [], [], [], []
        offset = 0
        geoms = scene_or_mesh.geometry.values() if hasattr(scene_or_mesh, "geometry") else [scene_or_mesh]
        for g in geoms:
            if hasattr(g, "vertices") and hasattr(g, "faces") and len(g.faces) > 0:
                verts = g.vertices; faces = g.faces
                vertices_all.append(verts)
                i += (faces[:,0]+offset).tolist()
                j += (faces[:,1]+offset).tolist()
                k += (faces[:,2]+offset).tolist()
                offset += len(verts)
        if not vertices_all:
            st.warning("No se encontraron caras trianguladas.")
        else:
            V = np.vstack(vertices_all)
            fig = go.Figure(data=[go.Mesh3d(x=V[:,0], y=V[:,1], z=V[:,2], i=i, j=j, k=k, opacity=1)])
            fig.update_layout(scene=dict(aspectmode="data"), margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"No se pudo visualizar GLB: {e}")