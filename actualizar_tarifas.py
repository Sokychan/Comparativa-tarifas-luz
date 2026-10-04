import json
import os
import importlib

# Diccionario que vincula el nombre del JSON con el nombre del archivo Python (sin el .py)
COMERCIALIZADORAS = {
    "Iberdrola": "scraper_iberdrola",
    "EnergyaVM": "scraper_energyavm",
    "Visalia": "scraper_visalia",
    "Octopus Energy": "scraper_octopus",
    "Nufri": "scraper_nufri",
    "Imagina energía": "scraper_imagina",
    "CHC Energía": "scraper_chc",
    "Naturgy": "scraper_naturgy",
    "Endesa": "scraper_endesa",
    "Totalenergies": "scraper_totalenergies"
}

def cargar_scraper(nombre_modulo):
    """Intenta importar el archivo .py de la comercializadora. Si no existe, devuelve None."""
    try:
        return importlib.import_module(nombre_modulo)
    except ImportError:
        return None

def actualizar_fichero_tarifas():
    ruta_json = "tarifas.json"
    
    if not os.path.exists(ruta_json):
        print(f"⚠️ Error crítico: No se encuentra el fichero {ruta_json}")
        return

    # 1. Cargar la base de datos
    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    print("🔄 Iniciando proceso de actualización modular...")

    # 2. Recorrer cada tarifa del JSON
    for tarifa in datos.get("tarifas", []):
        nombre = tarifa.get("Comercializadora", "")
        tipo = tarifa.get("Tipo", "")
        
        # Ignorar tarifas personalizadas introducidas por el usuario en la app
        if "(Actual)" in nombre or "Tu tarifa" in tipo:
            continue

        print(f"\n-> Analizando: {nombre} ({tipo})")

        # 3. Buscar qué archivo .py le corresponde a esta comercializadora
        modulo_nombre = COMERCIALIZADORAS.get(nombre)
        if not modulo_nombre:
            print(f"   ⚠️ Comercializadora '{nombre}' no está configurada en el diccionario interno.")
            continue

        # 4. Cargar el script de esa comercializadora
        scraper = cargar_scraper(modulo_nombre)
        if not scraper:
            print(f"   ⚠️ Módulo '{modulo_nombre}.py' no encontrado. Créalo para automatizar esta tarifa.")
            continue

        # 5. Determinar si es precio fijo o 3 periodos por el nombre en el JSON
        tipo_lower = tipo.lower()
        if any(keyword in tipo_lower for keyword in ["sin horarios", "24h", "24 horas", "24 h", "relax", "fijo", "fija"]):
            es_3p = False
        elif any(keyword in tipo_lower for keyword in ["3 periodos", "3p", "con horarios", "noche", "horarios", "ahorro", "octopus 3"]):
            es_3p = True
        else:
            es_3p = False
        
        nuevos_valores = None
        try:
            # Ejecutar la función correspondiente dentro de ese archivo
            if es_3p:
                if hasattr(scraper, 'obtener_precios_3p'):
                    nuevos_valores = scraper.obtener_precios_3p()
                else:
                    print(f"   ⚠️ La función 'obtener_precios_3p()' no existe en {modulo_nombre}.py")
            else:
                if hasattr(scraper, 'obtener_precios_fijo'):
                    nuevos_valores = scraper.obtener_precios_fijo()
                else:
                    print(f"   ⚠️ La función 'obtener_precios_fijo()' no existe en {modulo_nombre}.py")
        except Exception as e:
            print(f"   ❌ Error crítico al ejecutar {modulo_nombre}.py: {e}")

        # 6. Actualizar los datos si el scraper devolvió un diccionario
        if nuevos_valores:
            # Comprobar si devolvió 0 por un error de lectura/WAF
            if all(valor == 0 for clave, valor in nuevos_valores.items() if isinstance(valor, (int, float))):
                print(f"   ⚠️ El scraper devolvió valores a 0 (Posible bloqueo o fallo en la web).")
            else:
                print(f"   ✔ Extraído correctamente.")
            
            # Saneamiento de llaves según la modalidad capturada
            if es_3p:
                tarifa.pop("Precio_E_Fijo", None)
            else:
                tarifa.pop("Precio_E_Punta", None)
                tarifa.pop("Precio_E_Llano", None)
                tarifa.pop("Precio_E_Valle", None)

            # Sobrescribir los datos en el diccionario de la tarifa
            for clave, valor in nuevos_valores.items():
                tarifa[clave] = valor
        else:
            print(f"   ⚠️ No se devolvieron datos para {nombre}.")

    # 7. Guardar los cambios definitivos en el JSON
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print("\n🎉 ¡Proceso finalizado! Fichero tarifas.json actualizado.")

if __name__ == "__main__":
    actualizar_fichero_tarifas()
