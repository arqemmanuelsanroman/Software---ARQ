# =============================
# VISOR CLIMÁTICO Y URBANO 3D
# =============================

from ipyleaflet import (
    Map, DrawControl, basemaps, basemap_to_tiles,
    LayersControl, TileLayer, Marker, Polyline
)
from ipywidgets import Dropdown, VBox, HBox, Output
import json, requests, matplotlib.pyplot as plt, datetime

# --------------------------
# 1. Idioma y categorías
# --------------------------
idioma = Dropdown(
    options=[('Español', 'es'), ('English', 'en')],
    description='Idioma:',
    layout={'width': '200px'}
)

tipo = Dropdown(description='Uso:', layout={'width': '350px'})

categorias = {
    'es': ['Casa', 'Parque', 'Fraccionamiento', 'Rascacielos', 'Edificio histórico',
           'Jardín', 'Tienda', 'Supermercado', 'Canal', 'Río', 'Palacio', 'Ayuntamiento'],
    'en': ['House', 'Park', 'Residential Complex', 'Skyscraper', 'Historical Building',
           'Garden', 'Store', 'Supermarket', 'Canal', 'River', 'Palace', 'City Hall']
}

def actualizar_categorias(change):
    tipo.options = categorias[idioma.value]
    tipo.value = tipo.options[0]

idioma.observe(actualizar_categorias, names='value')
actualizar_categorias(None)

# --------------------------
# 2. Capas base
# --------------------------
capas_base = {
    "OpenStreetMap": basemap_to_tiles(basemaps.OpenStreetMap.Mapnik),
    "Satelite (Esri)": basemap_to_tiles(basemaps.Esri.WorldImagery),
    "Topográfico (Esri)": basemap_to_tiles(basemaps.Esri.WorldTopoMap),
    "Carto Positivo": basemap_to_tiles(basemaps.CartoDB.Positron),
    "Carto Oscuro": basemap_to_tiles(basemaps.CartoDB.DarkMatter),
    "Topográfico (OSM)": TileLayer(url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                                   attribution="© OpenTopoMap contributors"),
    "Transporte": TileLayer(url="https://tile.memomaps.de/tilegen/{z}/{x}/{y}.png",
                            attribution="© MemoMap & Public Transport Tiles")
}

selector_capa = Dropdown(
    options=list(capas_base.keys()),
    value="OpenStreetMap",
    description="Mapa:"
)

# --------------------------
# 3. Crear mapa y predio
# --------------------------
coordenadas_proyecto = (19.02889, -98.23010)
m = Map(center=coordenadas_proyecto, zoom=18, min_zoom=1, max_zoom=22)
capa_base_actual = capas_base[selector_capa.value]
m.add_layer(capa_base_actual)
m.add_layer(Marker(location=coordenadas_proyecto, draggable=False))

poligono_predio = [
    (19.02880, -98.23020),
    (19.02880, -98.22995),
    (19.02900, -98.22995),
    (19.02900, -98.23020),
    (19.02880, -98.23020)
]
m.add_layer(Polyline(locations=poligono_predio, color="red", weight=4, fill=False))

def actualizar_capa(change):
    global capa_base_actual
    nueva = capas_base[change.new]
    m.substitute_layer(capa_base_actual, nueva)
    capa_base_actual = nueva

selector_capa.observe(actualizar_capa, names='value')
m.add_control(LayersControl(position='topright'))

# --------------------------
# 4. Dibujo y clima
# --------------------------
draw_control = DrawControl()
m.add_control(draw_control)
salida = Output()

@draw_control.on_draw
def guardar_clasificado(target, action, geo_json):
    geo_json['properties'] = {
        'uso': tipo.value,
        'idioma': idioma.value
    }

    coords = geo_json["geometry"]["coordinates"][0]
    lon = sum(p[0] for p in coords) / len(coords)
    lat = sum(p[1] for p in coords) / len(coords)
    centroide = (lat, lon)
    m.add_layer(Marker(location=centroide, draggable=False))

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_speed_10m,wind_direction_10m,precipitation"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=auto"
    )

    try:
        r = requests.get(url).json()
        temp_c = r["current"]["temperature_2m"]
        temp_f = temp_c * 9/5 + 32
        viento = r["current"]["wind_speed_10m"]
        dir_viento = r["current"]["wind_direction_10m"]
        lluvia = r["current"]["precipitation"]
        lluvia_max = r["daily"]["precipitation_sum"][0]
        t_max = r["daily"]["temperature_2m_max"][0]
        t_min = r["daily"]["temperature_2m_min"][0]

        if idioma.value == 'es':
            print(f"\n✅ Guardado: {tipo.value} (Español)")
            print(f"📍 Centroide: {centroide}")
            print(f"🌡️ Temperatura actual: {temp_c} °C / {temp_f:.1f} °F")
            print(f"🔺 Máxima: {t_max} °C / 🔻 Mínima: {t_min} °C")
            print(f"🌬️ Viento: {viento} km/h, Dirección: {dir_viento}°")
            print(f"🌧️ Precipitación: Actual: {lluvia} mm | Máxima estimada: {lluvia_max} mm")
        else:
            print(f"\n✅ Saved: {tipo.value} (English)")
            print(f"📍 Centroid: {centroide}")
            print(f"🌡️ Current temperature: {temp_c} °C / {temp_f:.1f} °F")
            print(f"🔺 Max: {t_max} °C / 🔻 Min: {t_min} °C")
            print(f"🌬️ Wind: {viento} km/h, Direction: {dir_viento}°")
            print(f"🌧️ Precipitation: Now: {lluvia} mm | Max: {lluvia_max} mm")

        url_mensual = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={lat}&longitude={lon}"
            f"&start_date=2023-01-01&end_date=2023-12-31"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
            f"&timezone=auto"
        )

        datos = requests.get(url_mensual).json()
        fechas = [datetime.datetime.strptime(d, "%Y-%m-%d") for d in datos["daily"]["time"]]
        meses = [f.month for f in fechas]

        def promedio_mensual(valores):
            return [
                round(sum(v for v, m in zip(valores, meses) if m == mes) /
                      max(1, len([v for v, m in zip(valores, meses) if m == mes])), 1)
                for mes in range(1, 13)
            ]

        tmax = promedio_mensual(datos["daily"]["temperature_2m_max"])
        tmin = promedio_mensual(datos["daily"]["temperature_2m_min"])
        lluvia = promedio_mensual(datos["daily"]["precipitation_sum"])
        viento = promedio_mensual(datos["daily"]["wind_speed_10m_max"])
        etiquetas = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

        fig, axs = plt.subplots(3, 1, figsize=(10, 10), sharex=True)

        axs[0].plot(etiquetas, tmax, label='Máx °C', color='red', marker='o')
        axs[0].plot(etiquetas, tmin, label='Mín °C', color='blue', marker='o')
        axs[0].set_title("🌡️ Temperatura Promedio por Mes")
        axs[0].legend()

        axs[1].bar(etiquetas, lluvia, color='skyblue')
        axs[1].set_title("🌧️ Precipitación Total Mensual (mm)")

        axs[2].plot(etiquetas, viento, color='green', marker='s')
        axs[2].set_title("🌬️ Viento Máximo Promedio Mensual (km/h)")

        plt.xlabel("Meses")
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print("❌ Error al consultar clima:", e)

    with open("clasificado.geojson", "a") as f:
        json.dump(geo_json, f)
        f.write("\n")

# --------------------------
# 5. Mostrar interfaz
# --------------------------
VBox([
    HBox([idioma, tipo, selector_capa]),
    m,
    salida
])