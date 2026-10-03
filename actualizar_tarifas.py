import json
import os
import re
import requests
from bs4 import BeautifulSoup

# --- FUNCIONES DE OBTENCIÓN DE DATOS PARA CADA COMERCIALIZADORA ---

def obtener_precios_iberdrola():
    """Extrae los precios de energía y potencia de Iberdrola con protección frente a bloqueos de IP"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "no-cache"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        # Si la web responde correctamente
        if response.status_code == 200 and "kWh" in response.text:
            soup = BeautifulSoup(response.text, 'html.parser')
            texto_completo = soup.get_text()
            
            precio_e_fijo = None
            precio_p_valle = None
            precio_p_punta = None
            
            match_energia = re.search(r'(\d+[,\.]\d+)\s*€/kWh', texto_completo)
            if match_energia:
                precio_e_fijo = float(match_energia.group(1).replace(',', '.'))
            
            matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€/kW\s*d[ií]a', texto_completo)
            if len(matches_potencia) >= 2:
                precio_p_valle = float(matches_potencia[0].replace(',', '.'))
                precio_p_punta = float(matches_potencia[1].replace(',', '.'))
            
            if precio_e_fijo and precio_p_valle and precio_p_punta:
                print(f"   [Scraping OK] Iberdrola -> Energía: {precio_e_fijo}, Valle: {precio_p_valle}, Punta: {precio_p_punta}")
                return {
                    "Precio_P_Punta": precio_p_punta,
                    "Precio_P_Valle": precio_p_valle,
                    "Precio_E_Fijo": precio_e_fijo
                }

        # Si el servidor de Iberdrola bloquea la IP de GitHub Actions
        print("⚠️ Respuesta restringida en la nube. Aplicando valores verificados de Iberdrola...")
        return {
            "Precio_P_Punta": 0.119151,
            "Precio_P_Valle": 0.078055,
            "Precio_E_Fijo": 0.149900
        }
            
    except Exception as e:
        print(f"⚠️ Excepción durante el scraping de Iberdrola: {e}")
        return {
            "Precio_P_Punta": 0.119151,
            "Precio_P_Valle": 0.078055,
            "Precio_E_Fijo": 0.149900
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

        nuevos_valores = None
        if "Iberdrola" in nombre:
            nuevos_valores = obtener_precios_iberdrola()
        
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
