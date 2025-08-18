import folium
from folium.plugins import Draw

# Visor de Planeación Global
mapa = folium.Map(
    location=[0, 0],  # Centro del mundo (océano atlántico) como valor neutral,
    zoom_start=18,
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri'
)

# Añadir herramienta para dibujar polígonos
dibujar = Draw(export=True)
dibujar.add_to(mapa)

# Guardar el mapa como archivo HTML
mapa.save("mapa_interactivo.html")

print("✅ Mapa generado. Abre 'mapa_interactivo.html' para visualizarlo.")