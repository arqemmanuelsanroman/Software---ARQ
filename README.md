# 🌍 Bioclima 3D App

Aplicación interactiva en **Streamlit** que permite:
- Seleccionar una ubicación en un **mapa**.  
- Obtener datos climáticos **reales** (ERA5 vía [Open-Meteo](https://open-meteo.com/)) o cargar tus propios datos en **CSV**.  
- Generar un **modelo paramétrico 3D bioclimático** (torres mensuales).  
- Visualizar gráficas de temperatura, viento, radiación y alturas normalizadas.  
- Descargar el modelo 3D como **PNG**.  

---

## ⚙️ Requisitos

- Python **3.9+**
- Paquetes (instalar desde `requirements.txt`):

```bash
streamlit
folium
streamlit-folium
matplotlib
numpy
pandas
requests
```

---

## 📦 Instalación

1. Clonar el repo o copiar los archivos (`app.py` y `requirements.txt`).
2. Crear entorno virtual (opcional pero recomendado):

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate    # Windows
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

---

## ▶️ Ejecución

Lanzar la app con:

```bash
streamlit run app.py
```

Se abrirá en tu navegador en `http://localhost:8501`.

---

## 📂 Uso

1. **Selecciona ubicación en el mapa** (click sobre el punto deseado).  
2. **Opciones de entrada** (en la barra lateral):
   - Subir CSV con columnas:  
     `tmax, tmin, viento[, radiacion]` (12 filas, una por mes).  
   - O usar **datos reales de Open-Meteo** (seleccionando año histórico).  
   - O usar datos ficticios (dummy) si desactivas Open-Meteo.  
3. Ajustar parámetros:
   - Elevación y azimut de cámara.  
   - Tamaño base, escala y separación de las torres.  
4. Presionar **Diseño Bioclimático**.  
5. Se mostrará:
   - Modelo 3D.  
   - Gráficas de temperatura, viento, radiación y alturas.  
   - Botón para descargar el 3D como PNG.  

---

## 📊 Ejemplo de CSV esperado

```csv
mes,tmax,tmin,viento,radiacion
Ene,25,10,3,150
Feb,27,12,3.5,160
Mar,30,15,4,180
Abr,32,18,4.5,200
May,35,20,5,220
Jun,36,21,5.2,230
Jul,34,20,4.8,210
Ago,33,19,4.5,200
Sep,31,18,4.2,190
Oct,29,16,3.8,170
Nov,27,14,3.5,160
Dic,25,11,3,150
```

---

## 🛰️ Notas

- Si la descarga de Open-Meteo falla, la app **cambia automáticamente** a una serie dummy.  
- El loader bloquea la interfaz mientras se descarga y procesa la información.  
- Puedes reintentar con el botón **“Reintentar descarga”**.  
