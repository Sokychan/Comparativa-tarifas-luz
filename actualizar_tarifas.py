import json
import os

# --- FUNCIONES DE OBTENCIÓN DE DATOS PARA CADA COMERCIALIZADORA ---
# Aquí es donde en el futuro integrarás tu lógica de web scraping o llamadas a APIs.

def obtener_precios_iberdrola():
    """TODO: Realizar scraping en la web de Iberdrola"""
    # Simulamos nuevos valores extraídos de la web
    return {
        "Precio_P_Punta": 0.1120,
        "Precio_P_Valle": 0.0310,
        "Precio_E_Fijo": 0.1450
    }

def obtener_precios_endesa():
    """TODO: Realizar scraping en la web de Endesa"""
    return {
        "Precio_P_Punta": 0.1070,
        "Precio_P_Valle": 0.0290,
        "Precio_E_Fijo": 0.1400
    }

def obtener_precios_octopus():
    """TODO: Realizar scraping en la web de Octopus Energy"""
    return {
        "Precio_P_Punta": 0.0920,
        "Precio_P_Valle": 0.0260,
        "Precio_E_Fijo": 0.1320
    }

def obtener_precios_naturgy():
    """TODO: Realizar scraping en la web de Naturgy"""
    return {
        "Precio_P_Punta": 0.0960,
        "Precio_P_Valle": 0.0230,
        "Precio_E_Punta": 0.1720,
        "Precio_E_Llano": 0.1420,
        "Precio_E_Valle": 0.1020
    }

def obtener_precios_pvpc():
    """El PVPC se puede consultar directamente mediante la API oficial de ESIOS / REE"""
    # Simulamos la lectura oficial
    return {
        "Precio_P_Punta": 0.0820,
        "Precio_P_Valle": 0.0210,
        "Precio_E_Punta": 0.1650,
        "Precio_E_Llano": 0.1320,
        "Precio_E_Valle": 0.0910
    }


def actualizar_fichero_tarifas():
    ruta_json = "tarifas.json"
    
    if not os.path.exists(ruta_json):
        print(f"⚠️ Error crítico: No se encuentra el fichero {ruta_json}")
        return

    # 1. Cargamos el fichero JSON actual
    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    print("🔄 Iniciando proceso de actualización de tarifas de mercado...")

    # 2. Recorremos dinámicamente cada tarifa registrada en el JSON
    for tarifa in datos.get("tarifas", []):
        nombre = tarifa.get("Comercializadora", "")
        
        # Ignoramos si es la tarifa personalizada introducida por un usuario local en la app
        if "(Actual)" in nombre or "Tu tarifa" in tarifa.get("Tipo", ""):
            continue

        print(f"-> Actualizando comercializadora: {nombre}...")

        # Asignamos la función de obtención de datos según el nombre de la empresa
        nuevos_valores = None
        if "Iberdrola" in nombre:
            nuevos_valores = obtener_precios_iberdrola()
        elif "Endesa" in nombre:
            nuevos_valores = obtener_precios_endesa()
        elif "Octopus" in nombre:
            nuevos_valores = obtener_precios_octopus()
        elif "Naturgy" in nombre:
            nuevos_valores = obtener_precios_naturgy()
        elif "PVPC" in nombre:
            nuevos_valores = obtener_precios_pvpc()
        
        # Si hemos obtenido nuevos valores, actualizamos las claves dinámicamente
        if nuevos_valores:
            for clave, valor in nuevos_valores.items():
                tarifa[clave] = valor
            print(f"   ✔ {nombre} actualizada con éxito.")
        else:
            print(f"   ⚠️ No hay rutina de actualización definida para {nombre}.")

    # 3. Guardamos los cambios de vuelta en el fichero tarifas.json
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print("🎉 ¡Proceso finalizado! Fichero tarifas.json guardado correctamente.")

if __name__ == "__main__":
    actualizar_fichero_tarifas()
