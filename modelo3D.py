import json
import pydeck as pdk
from shapely.geometry import shape

# Cargar el archivo GeoJSON exportado desde el visor
with open("poligono.geojson") as f:
    geojson = json.load(f)

# Extraer el polígono del archivo
geom = shape(geojson['features'][0]['geometry'])

# Obtener coordenadas promedio para centrar el visor
coords = geom.centroid.coords[0]

# Crear una capa en 3D (extrusión)
layer = pdk.Layer(
    "PolygonLayer",
    data=geojson['features'],
    get_polygon="geometry.coordinates",
    get_fill_color="[200, 30, 0, 160]",
    get_elevation=20,  # altura del volumen (en metros)
    extruded=True,
    pickable=True,
    stroked=True
)

view_state = pdk.ViewState(
    latitude=coords[1],
    longitude=coords[0],
    zoom=18,
    pitch=45,
    bearing=0
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/satellite-v9"
)

deck.to_html("modelo3D.html")
print("✅ Modelo 3D generado. Abre 'modelo3D.html'")
