# Generador_Rascacielos_Bioclimatico.py

# Función reutilizable para ingresar valores numéricos con unidades o separadores
def leer_float_con_unidades(prompt):
    valor = input(prompt)
    valor = valor.replace(",", "")  # quita separador de miles
    valor = valor.replace("m²", "").replace("m2", "").replace("m", "").replace("metros", "")
    valor = valor.strip()
    return float(valor)

# 1. Ubicación y tipología del proyecto
def definir_ubicacion_y_tipologia():
    print("\n--- Ubicación y Tipología del Proyecto ---")
    tipologia = input("Tipología del proyecto (rascacielos, edificio, casa, parque, etc.): ")
    latitud = leer_float_con_unidades("Latitud: ")
    longitud = leer_float_con_unidades("Longitud: ")
    return {
        "tipologia": tipologia,
        "latitud": latitud,
        "longitud": longitud
    }

# 2. Dimensiones y mecánica de suelos
def definir_dimensiones_y_suelos():
    print("\n--- Ingresar dimensiones del proyecto ---")
    modo = input("¿Quieres ingresar las dimensiones por frente/fondo o directamente en m²? (escribe 'f' o 'm2'): ").lower()

    if modo == 'm2':
        area = leer_float_con_unidades("Área total del proyecto (m²): ")
        frente = None
        fondo = None
        altura = leer_float_con_unidades("Altura aproximada del proyecto (m): ")
    else:
        frente = leer_float_con_unidades("Frente del proyecto (m): ")
        fondo = leer_float_con_unidades("Fondo del proyecto (m): ")
        altura = leer_float_con_unidades("Altura aproximada del proyecto (m): ")
        area = frente * fondo

    suelo = input("Descripción del análisis de mecánica de suelos: ")

    return {
        "frente": frente,
        "fondo": fondo,
        "altura": altura,
        "area_m2": area,
        "mecanica_suelos": suelo
    }

# 3. Datos del sitio (calculados o introducidos manualmente)
def definir_condiciones_del_sitio():
    print("\n--- Datos del sitio (pueden ser estimados o reales) ---")
    vientos = input("Vientos dominantes: ")
    asoleamiento = input("Exposición solar diaria/anual (orientación, horas, etc.): ")
    captacion = input("Posibilidades de captación pluvial o residual: ")
    energia = input("¿Cómo se puede aprovechar la luz solar o el viento para generar energía?: ")
    return {
        "vientos_dominantes": vientos,
        "exposicion_solar": asoleamiento,
        "captacion_agua": captacion,
        "aprovechamiento_energia": energia
    }

# 4. Diseño arquitectónico base
def seleccionar_diseno_referencia():
    print("\n--- Selecciona o describe el diseño arquitectónico base ---")
    referencia = input("Descripción del diseño o proyecto base de inspiración: ")
    return referencia

# 5. Mostrar resumen completo
def mostrar_resumen(ubicacion, dimensiones, condiciones, referencia):
    print("\n========== RESUMEN DEL PROYECTO ==========")
    print("Tipología:", ubicacion["tipologia"])
    print("Ubicación: Lat", ubicacion["latitud"], "/ Lon", ubicacion["longitud"])

    if dimensiones["frente"] and dimensiones["fondo"]:
        print("Dimensiones: Frente:", dimensiones["frente"], "m / Fondo:", dimensiones["fondo"], "m / Altura:", dimensiones["altura"], "m")
    else:
        print("Altura aproximada:", dimensiones["altura"], "m (frente y fondo no definidos por terreno irregular)")
    
    print("Área total del proyecto:", dimensiones["area_m2"], "m²")

    print("Condiciones del sitio:")
    print("  - Vientos dominantes:", condiciones["vientos_dominantes"])
    print("  - Exposición solar:", condiciones["exposicion_solar"])
    print("  - Captación de agua:", condiciones["captacion_agua"])
    print("  - Generación energética (solar/eólica):", condiciones["aprovechamiento_energia"])

    print("Diseño base de referencia:", referencia)

# 6. Ejecución del programa
if __name__ == "__main__":
    print("Bienvenido al generador de propuestas arquitectónicas bioclimáticas")
    ubicacion = definir_ubicacion_y_tipologia()
    dimensiones = definir_dimensiones_y_suelos()
    condiciones = definir_condiciones_del_sitio()
    referencia = seleccionar_diseno_referencia()
    mostrar_resumen(ubicacion, dimensiones, condiciones, referencia)