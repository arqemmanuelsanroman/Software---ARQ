# app.py
# Streamlit app: Mapa -> elegir ubicación -> generar modelo 3D y gráficas
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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Config ---
st.set_page_config(page_title="Bioclima 3D", layout="wide")

# --- Constantes ---
MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]

# Estado global para bloquear UI mientras se procesa
if "busy" not in st.session_state:
    st.session_state["busy"] = False
BUSY = st.session_state.get("busy", False)

# --- Utilidades de clima (dummy o desde CSV) ---
def series_dummy(n=12, lat=0.0):
    m = np.arange(n)
    # Ajuste leve por latitud para que no sea completamente fijo
    k = np.clip(abs(lat)/90.0, 0, 1)
    tmax = 30 + (6+4*k) * np.sin(2*np.pi*(m-2)/n)
    tmin = 15 + (5+2*k) * np.sin(2*np.pi*(m-3)/n)
    viento = 4 + (1.2+0.6*k) * np.sin(2*np.pi*(m+1)/n)
    radiacion = 180 + (50+30*k) * np.sin(2*np.pi*(m-2)/n)
    return tmax, tmin, viento, radiacion

def alturas_conceptuales(tmax, viento, radiacion=None):
    rad = np.zeros_like(tmax) if radiacion is None else radiacion
    h = tmax + 0.5*viento + 0.1*rad
    max_h = float(np.max(h)) if np.any(np.isfinite(h)) else 1.0
    if max_h == 0:
        max_h = 1.0
    return (h / max_h) * 100.0

def plot_modelo_3d(alturas, elev=25, azim=210, paso=5.0, escala=0.15, torre_xy=1.0, alpha=0.85):
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111, projection='3d')
    for i, h in enumerate(alturas):
        x = np.array([-torre_xy, -torre_xy,  torre_xy,  torre_xy], dtype=float)
        y = np.array([-torre_xy,  torre_xy,  torre_xy, -torre_xy], dtype=float)
        z_base = i * paso
        z_top = z_base + float(h) * escala
        base = list(zip(x, y, [z_base]*4))
        top = list(zip(x, y, [z_top]*4))
        caras = [base, top]
        poly = Poly3DCollection(caras, facecolor=cm.viridis(i / max(1, len(alturas)-1)), alpha=alpha)
        ax.add_collection3d(poly)
        ax.text(torre_xy*1.2, torre_xy*1.2, z_base, MESES[i % 12], fontsize=8, zdir='x')
    ax.set_title("Modelo Paramétrico Bioclimático del Rascacielos")
    ax.set_xlabel("Eje X"); ax.set_ylabel("Eje Y"); ax.set_zlabel("Altura (conceptual)")
    ax.view_init(elev=elev, azim=azim)
    zmax = len(alturas) * paso + 30
    ax.set_zlim(0, zmax)
    plt.tight_layout()
    return fig

def line_chart(values, title, ylabel):
    fig = plt.figure(figsize=(4, 3))
    plt.plot(range(1, len(values)+1), values, marker='o')
    plt.title(title)
    plt.xlabel("Mes"); plt.ylabel(ylabel)
    plt.xticks(range(1, 13), MESES, rotation=0)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig

# --- HTTP con reintentos ---
def requests_retry_session(
    retries: int = 3,
    backoff_factor: float = 2.0,
    status_forcelist: tuple = (429, 500, 502, 503, 504),
    allowed_methods: frozenset = frozenset(["GET"]),
) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

# --- Datos reales desde Open-Meteo (histórico ERA5) ---
def fetch_open_meteo_monthly(lat: float, lon: float, year: int | None = None):
    """
    Descarga datos diarios del archivo ERA5 de Open-Meteo para un año y los agrega a 12 meses.
    Retorna tmax, tmin, viento, radiacion como arrays de 12.
    """
    if year is None:
        # último año completo disponible (el año anterior al actual)
        year = date.today().year - 1

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "wind_speed_10m_max",
            "shortwave_radiation_sum"
        ],
        "timezone": "auto"
    }
    base = "https://archive-api.open-meteo.com/v1/era5"
    resp = requests_retry_session().get(base, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame({
        "date": pd.to_datetime(data["daily"]["time"]),
        "tmax": data["daily"]["temperature_2m_max"],
        "tmin": data["daily"]["temperature_2m_min"],
        "viento": data["daily"]["wind_speed_10m_max"],
        "rad": data["daily"]["shortwave_radiation_sum"],
    }).set_index("date")

    # Agregación mensual
    m = df.resample("MS").agg({
        "tmax": "mean",
        "tmin": "mean",
        "viento": "mean",
        "rad": "sum"
    }).iloc[:12]

    # Completar si faltan meses
    if len(m) < 12:
        m = m.reindex(pd.date_range(f"{year}-01-01", periods=12, freq="MS"))
    m = m.fillna(method="ffill").fillna(method="bfill")

    return (
        m["tmax"].to_numpy(),
        m["tmin"].to_numpy(),
        m["viento"].to_numpy(),
        m["rad"].to_numpy()
    )

# --- UI ---
st.title("Diseño Bioclimático: Mapa → Modelo 3D → Gráficas")

with st.sidebar:
    st.header("Entrada de datos")
    uploaded = st.file_uploader(
        "CSV con columnas: tmax,tmin,viento[,radiacion] (12 filas)",
        type=["csv"],
        disabled=BUSY
    )
    elev = st.slider("Elevación cámara (3D)", 0, 85, 25, disabled=BUSY)
    azim = st.slider("Azimut cámara (3D)", 0, 360, 210, disabled=BUSY)

    st.header("Fuente de datos")
    usar_openmeteo = st.checkbox("Usar datos reales (Open-Meteo ERA5)", value=True, disabled=BUSY)
    anio = st.number_input("Año histórico", min_value=1979, max_value=2100, value=(date.today().year - 1), disabled=BUSY)

    st.header("Parámetros del modelo 3D")
    paso = st.slider("Separación entre torres (paso)", 2, 20, 5, disabled=BUSY)
    escala = st.slider("Escala de altura", 0.05, 0.5, 0.15, disabled=BUSY)
    base = st.slider("Tamaño base de la torre", 1, 5, 1, disabled=BUSY)

st.subheader("1) Elige una ubicación en el mapa (click)")
center = (19.4326, -99.1332)  # CDMX por defecto
m = folium.Map(location=center, zoom_start=5, control_scale=True)
folium.TileLayer("OpenStreetMap").add_to(m)
folium.LatLngPopup().add_to(m)

map_data = (None if BUSY else st_folium(m, height=450, width=None))

# Obtener la última coordenada clickeada
lat, lon = None, None
if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

col1, col2, col3 = st.columns([1,1,1])
with col1:
    lat = st.number_input("Latitud", value=float(lat) if lat is not None else center[0], format="%.6f", disabled=BUSY)
with col2:
    lon = st.number_input("Longitud", value=float(lon) if lon is not None else center[1], format="%.6f", disabled=BUSY)
with col3:
    run = st.button("Diseño Bioclimático", type="primary", use_container_width=True, disabled=BUSY)
    retry = st.button("Reintentar descarga", use_container_width=True, disabled=BUSY)

st.divider()

if run or retry:
    st.session_state["busy"] = True
    BUSY = True
    with st.spinner("Descargando datos y generando diseño..."):
        try:
            # Cargar datos
            if uploaded is not None:
                df = pd.read_csv(uploaded)
                cols = {c.lower(): c for c in df.columns}
                def get_col(*names):
                    for n in names:
                        if n in cols:
                            return df[cols[n]].to_numpy().astype(float)[:12]
                    return None
                tmax = get_col("tmax","temp_max","tempmax")
                tmin = get_col("tmin","temp_min","tempmin")
                viento = get_col("viento","wind","wind_speed","vel_viento")
                radiacion = get_col("radiacion","radiation","rad")
                if tmax is None or tmin is None or viento is None:
                    st.error("El CSV debe tener al menos columnas para tmax, tmin y viento (12 filas).")
                    st.stop()
                if radiacion is not None and len(radiacion) < 12:
                    radiacion = None
                tmax = tmax[:12]; tmin = tmin[:12]; viento = viento[:12]
                if radiacion is not None:
                    radiacion = radiacion[:12]
            else:
                if usar_openmeteo:
                    try:
                        tmax, tmin, viento, radiacion = fetch_open_meteo_monthly(lat, lon, int(anio))
                    except Exception as e:
                        st.warning(f"No se pudo descargar Open-Meteo ({e}). Usando serie dummy.")
                        tmax, tmin, viento, radiacion = series_dummy(12, lat=lat)
                else:
                    tmax, tmin, viento, radiacion = series_dummy(12, lat=lat)

            alturas = alturas_conceptuales(tmax, viento, radiacion)

            # --- Mostrar 3D ---
            fig3d = plot_modelo_3d(alturas, elev=elev, azim=azim, paso=paso, escala=escala, torre_xy=base)
            st.pyplot(fig3d, use_container_width=False)

            # --- Gráficas simples ---
            col_a, col_b = st.columns(2)
            with col_a:
                st.pyplot(line_chart(tmax, "Temperatura Máxima", "°C"), use_container_width=False)
                st.pyplot(line_chart(viento, "Viento", "m/s"), use_container_width=False)
            with col_b:
                if radiacion is not None:
                    st.pyplot(line_chart(radiacion, "Radiación", "W/m²"), use_container_width=False)
                st.pyplot(line_chart(alturas, "Alturas Conceptuales Normalizadas", "%"), use_container_width=False)

            # Descargar imagen 3D
            buf = BytesIO()
            fig3d.savefig(buf, format="png", dpi=200, bbox_inches="tight")
            st.download_button("Descargar 3D como PNG", data=buf.getvalue(), file_name="bioclima_3d.png", mime="image/png")

            st.success("Listo ✅")
        except Exception as e:
            st.error(f"Ocurrió un error: {e}")
        finally:
            st.session_state["busy"] = False
            BUSY = False
else:
    st.info("Haz click en el mapa para fijar lat/lon (o edítalos manualmente) y luego pulsa **Diseño Bioclimático**.")
