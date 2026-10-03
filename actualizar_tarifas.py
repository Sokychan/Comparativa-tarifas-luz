import json
import os
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def limpiar_html_agresivo(html_text):
    """Elimina todas las etiquetas HTML y decodifica entidades para evitar que rompan la lectura."""
    texto = html_text.replace('&euro;', '€').replace('&#8364;', '€').replace('&nbsp;', ' ')
    texto_sin_tags = re.sub(r'<[^>]+>', ' ', texto)
    return ' '.join(texto_sin_tags.split())

def obtener_html_con_navegador(url):
    """Abre la web configurando huella digital humana para evitar el bloqueo por IP/WAF."""
    try:
        with sync_playwright() as p:
            # Banderas de Chromium para ocultar que es una instancia automatizada
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--window-size=1920,1080"
                ]
            )
            
            # Perfil con geolocalización, zona horaria e idioma de España
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="es-ES",
                timezone_id="Europe/Madrid",
                extra_http_headers={
                    "Accept-Language": "es-ES,es;q=0.9",
                    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                }
            )
            
            page = context.new_page()
            
            # Inyección para eliminar la propiedad 'navigator.webdriver' que delata a los bots
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # Navegar simulando comportamiento humano
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000) # Espera 3 segundos para renderizado de JS
            
            content = page.content()
            browser.close()
            return content
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en {url}: {e}")
        return None

# --- FUNCIONES DE OBTENCIÓN DE DATOS PARA CADA COMERCIALIZADORA ---

def obtener_precios_iberdrola_fijo():
    """Extrae los precios del Plan Online (Precio Fijo 24h) de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    html_content = obtener_html_con_navegador(url)
    if not html_content:
        return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html_content)
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)

        # --- LÍNEAS DE DEPURACIÓN ---
        print(f"🔍 [DEBUG] Longitud texto extraído: {len(texto_limpio)} caracteres.")
        print(f"🔍 [DEBUG] Muestras de energía encontradas: {matches_energia}")
        print(f"🔍 [DEBUG] Muestras de potencia encontradas: {matches_potencia}")
        # -----------------------------
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.05 <= float(p.replace(',', '.')) <= 0.40]
        precios_p = sorted(list(set([float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.30])))
        
        if precios_e and len(precios_p) >= 2:
            return {
                "Precio_P_Punta": precios_p[-1], # El valor más alto
                "Precio_P_Valle": precios_p[0],  # El valor más bajo
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron filtrar los valores numéricos de Iberdrola Fijo. Devolviendo 0...")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola Fijo: {e}. Devolviendo 0...")
        return error_return

def obtener_precios_iberdrola_3p():
    """Extrae los precios del Plan Online 3 Periodos de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    html_content = obtener_html_con_navegador(url)
    if not html_content:
        return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html_content)
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
        
        precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
        precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.30]
        
        precios_e_unicos = []
        for p in precios_e_raw:
            if not precios_e_unicos or precios_e_unicos[-1] != p:
                precios_e_unicos.append(p)
                
        precios_p_unicos = sorted(list(set(precios_p_raw)))
        
        if len(precios_e_unicos) >= 3 and len(precios_p_unicos) >= 2:
            precios_e_ordenados = sorted(precios_e_unicos[:3])
            
            return {
                "Precio_P_Punta": precios_p_unicos[-1],  # El más alto
                "Precio_P_Valle": precios_p_unicos[0],   # El más bajo
                "Precio_E_Punta": precios_e_ordenados[-1], # El más alto
                "Precio_E_Llano": precios_e_ordenados[1],  # Medio
                "Precio_E_Valle": precios_e_ordenados[0]   # El más bajo
            }

        print("⚠ No se pudieron filtrar los precios de Iberdrola 3P correctamente. Devolviendo 0...")
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
        print(f"⚠ Error crítico: No se encuentra el fichero {ruta_json}")
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
