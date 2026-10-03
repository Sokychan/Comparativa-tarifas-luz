import json
import os
import re
import requests
from bs4 import BeautifulSoup

# --- FUNCIONES DE OBTENCIÓN DE DATOS PARA CADA COMERCIALIZADORA ---

def obtener_precios_iberdrola_fijo():
    """Extrae los precios del Plan Online (Precio Fijo 24h) de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "no-cache"
    }
    
    error_return = {
        "Precio_P_Punta": 0,
        "Precio_P_Valle": 0,
        "Precio_E_Fijo": 0
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200 and "kWh" in response.text:
            soup = BeautifulSoup(response.text, 'html.parser')
            texto_limpio = ' '.join(soup.get_text(separator=' ').split())
            
            match_energia = re.search(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
            matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
            potencias_validas = [float(p.replace(',', '.')) for p in matches_potencia if 0.01 <= float(p.replace(',', '.')) <= 0.30]
            
            if match_energia and len(potencias_validas) >= 2:
                precio_e_fijo = float(match_energia.group(1).replace(',', '.'))
                print(f"   [Scraping OK] Iberdrola Fijo -> Energía: {precio_e_fijo}, Valle: {potencias_validas[0]}, Punta: {potencias_validas[1]}")
                return {
                    "Precio_P_Punta": potencias_validas[1],
                    "Precio_P_Valle": potencias_validas[0],
                    "Precio_E_Fijo": precio_e_fijo
                }

        print("⚠️ Error o restricción en Iberdrola Fijo. Devolviendo 0...")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola Fijo: {e}. Devolviendo 0...")
        return error_return

def obtener_precios_iberdrola_3p():
    """Extrae los precios del Plan Online 3 Periodos de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Cache-Control": "no-cache"
    }
    
    error_return = {
        "Precio_P_Punta": 0,
        "Precio_P_Valle": 0,
        "Precio_E_Punta": 0,
        "Precio_E_Llano": 0,
        "Precio_E_Valle": 0
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for element in soup(["script", "style", "header", "footer", "nav"]):
                element.extract()
                
            texto_limpio = ' '.join(soup.get_text(separator=' ').split())
            
            # Extracción y filtrado de precios de energía en rangos lógicos de mercado (0.03€ a 0.60€)
            matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
            precios_energia = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
            
            # Filtrar duplicados consecutivos (común en maquetaciones web responsive)
            precios_unicos = []
            for p in precios_energia:
                if not precios_unicos or precios_unicos[-1] != p:
                    precios_unicos.append(p)
            
            # Extracción y filtrado de precios de potencia (€/kW día)
            matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
            potencias_validas = [float(p.replace(',', '.')) for p in matches_potencia if 0.01 <= float(p.replace(',', '.')) <= 0.30]
            
            if len(precios_unicos) >= 3 and len(potencias_validas) >= 2:
                print(f"   [Scraping OK] Iberdrola 3P -> E.Punta: {precios_unicos[0]}, E.Llano: {precios_unicos[1]}, E.Valle: {precios_unicos[2]} | P.Punta: {potencias_validas[1]}, P.Valle: {potencias_validas[0]}")
                return {
                    "Precio_P_Punta": potencias_validas[1],
                    "Precio_P_Valle": potencias_validas[0],
                    "Precio_E_Punta": precios_unicos[0],
                    "Precio_E_Llano": precios_unicos[1],
                    "Precio_E_Valle": precios_unicos[2]
                }

        print("⚠️ No se pudieron extraer los precios de Iberdrola 3P correctamente. Devolviendo 0...")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola 3P: {e}. Devolviendo 0...")
        return error_return

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

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    print("🔄 Iniciando proceso de actualización de tarifas de mercado...")

    for tarifa in datos.get("tarifas", []):
        nombre = tarifa.get("Comercializadora", "")
        tipo = tarifa.get("Tipo", "")
        
        if "(Actual)" in nombre or "Tu tarifa" in tipo:
            continue

        print(f"-> Actualizando comercializadora: {nombre} ({tipo})...")

        nuevos_valores = None
        if "Iberdrola" in nombre:
            if "3 Periodos" in tipo or "3 periodos" in tipo.lower() or "tres" in tipo.lower():
                nuevos_valores = obtener_precios_iberdrola_3p()
            else:
                nuevos_valores = obtener_precios_iberdrola_fijo()
        elif "Endesa" in nombre:
            nuevos_valores = obtener_precios_endesa()
        elif "Octopus" in nombre:
            nuevos_valores = obtener_precios_octopus()
        elif "Naturgy" in nombre:
            nuevos_valores = obtener_precios_naturgy()
        elif "PVPC" in nombre:
            nuevos_valores = obtener_precios_pvpc()
        
        if nuevos_valores:
            for clave, valor in nuevos_valores.items():
                tarifa[clave] = valor
            print(f"   ✔ {nombre} ({tipo}) procesada.")
        else:
            print(f"   ⚠ No hay rutina definida para {nombre}.")

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print("🎉 ¡Proceso finalizado! Fichero tarifas.json guardado correctamente.")

if __name__ == "__main__":
    actualizar_fichero_tarifas()
