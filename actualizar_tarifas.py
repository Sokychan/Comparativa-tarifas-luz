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
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000) # Espera 3 segundos para el renderizado del DOM
            
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
        
        # Para la energía Fija, el primer valor válido de la página suele ser la tarjeta principal
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        
        # Para potencia, usamos búsqueda contextual anclada al nombre del periodo
        match_p_valle = re.search(r'Periodo Valle.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
        match_p_punta = re.search(r'Periodo Punta.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.05 <= float(p.replace(',', '.')) <= 0.40]
        
        if precios_e and match_p_valle and match_p_punta:
            return {
                "Precio_P_Punta": float(match_p_punta.group(1).replace(',', '.')),
                "Precio_P_Valle": float(match_p_valle.group(1).replace(',', '.')),
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron filtrar los valores numéricos exactos de Iberdrola Fijo. Devolviendo 0...")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola Fijo: {e}. Devolviendo 0...")
        return error_return

def obtener_precios_iberdrola_3p():
    """Extrae los precios del Plan Online 3 Periodos de Iberdrola con precisión posicional"""
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
        
        # Búsqueda contextual exacta vinculando la etiqueta temporal al bloque de energía (€/kWh)
        match_e_valle = re.search(r'Periodo Valle.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        match_e_llano = re.search(r'Periodo Llano.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        match_e_punta = re.search(r'Periodo Punta.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        
        # Búsqueda contextual exacta vinculando la etiqueta temporal al bloque de potencia (€/kW día)
        match_p_valle = re.search(r'Periodo Valle.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
        match_p_punta = re.search(r'Periodo Punta.{0,50}?(\d+[,\.]\d+)\s*€\s*/\s*kW\s*(?:d[ií]a|día)', texto_limpio, re.IGNORECASE)
        
        if match_e_valle and match_e_llano and match_e_punta and match_p_valle and match_p_punta:
            return {
                "Precio_P_Punta": float(match_p_punta.group(1).replace(',', '.')),
                "Precio_P_Valle": float(match_p_valle.group(1).replace(',', '.')),
                "Precio_E_Punta": float(match_e_punta.group(1).replace(',', '.')),
                "Precio_E_Llano": float(match_e_llano.group(1).replace(',', '.')),
                "Precio_E_Valle": float(match_e_valle.group(1).replace(',', '.'))
            }

        print("⚠ No se encontraron los identificadores estructurales de los periodos. Devolviendo 0...")
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
