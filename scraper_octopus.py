import re
from playwright.sync_api import sync_playwright

def limpiar_html_agresivo(html_text):
    """Elimina etiquetas HTML y normaliza espacios."""
    texto = html_text.replace('&euro;', '€').replace('&#8364;', '€').replace('&nbsp;', ' ')
    texto_sin_tags = re.sub(r'<[^>]+>', ' ', texto)
    return ' '.join(texto_sin_tags.split())

def obtener_html_con_navegador(url):
    """Abre la web configurando huella digital humana para evitar bloqueos."""
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
                timezone_id="Europe/Madrid"
            )
            
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(3000) # Espera para asegurar que los scripts visuales carguen
            
            content = page.content()
            browser.close()
            return content
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Octopus: {e}")
        return None

def extraer_bloque(texto, inicio_str, delimitadores_fin):
    """Recorta el texto desde una palabra clave hasta que encuentra otra tarifa."""
    idx_ini = texto.find(inicio_str)
    if idx_ini == -1:
        return ""
    
    idx_fin = len(texto)
    for d in delimitadores_fin:
        idx = texto.find(d, idx_ini + len(inicio_str))
        if idx != -1 and idx < idx_fin:
            idx_fin = idx
            
    return texto[idx_ini:idx_fin]

def obtener_precios_fijo():
    """Extrae los precios de la tarifa 'Octopus Relax' (Fija 24h)"""
    url = "https://octopusenergy.es/precios"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    html = obtener_html_con_navegador(url)
    if not html: return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html).lower()
        
        # Aislamiento de la columna Octopus Relax
        bloque = extraer_bloque(texto_limpio, "octopus relax", ["octopus flexi", "octopus 3"])
        
        if not bloque:
            print("⚠️ No se encontró la sección 'Octopus Relax'.")
            return error_return

        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', bloque)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', bloque)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.05 <= float(p.replace(',', '.')) <= 0.40]
        precios_p = sorted(list(set([float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.30])))
        
        if precios_e and len(precios_p) >= 2:
            return {
                "Precio_P_Punta": precios_p[-1], # El más alto es Punta
                "Precio_P_Valle": precios_p[0],  # El más bajo es Valle
                "Precio_E_Fijo": precios_e[0]
            }
            
        print("⚠️ No se pudieron extraer valores numéricos completos de Octopus Relax.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Octopus Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae los precios de la tarifa 'Octopus 3' (3 Periodos)"""
    url = "https://octopusenergy.es/precios"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0}
    
    html = obtener_html_con_navegador(url)
    if not html: return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html).lower()
        
        # Aislamiento de la columna Octopus 3
        bloque = extraer_bloque(texto_limpio, "octopus 3", ["te recomendamos", "octopus relax", "octopus flexi"])
        
        if not bloque:
            print("⚠️ No se encontró la sección 'Octopus 3'.")
            return error_return

        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', bloque)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', bloque)
        
        precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
        precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.30]
        
        # Eliminar duplicados consecutivos
        precios_e_unicos = []
        for p in precios_e_raw:
            if not precios_e_unicos or precios_e_unicos[-1] != p:
                precios_e_unicos.append(p)
                
        precios_p = sorted(list(set(precios_p_raw)))
        
        if len(precios_e_unicos) >= 3 and len(precios_p) >= 2:
            precios_e_ordenados = sorted(precios_e_unicos[:3])
            
            return {
                "Precio_P_Punta": precios_p[-1],
                "Precio_P_Valle": precios_p[0],
                "Precio_E_Punta": precios_e_ordenados[-1], # El más alto
                "Precio_E_Llano": precios_e_ordenados[1],  # El medio
                "Precio_E_Valle": precios_e_ordenados[0]   # El más bajo
            }
            
        print("⚠️ No se pudieron extraer valores numéricos completos de Octopus 3.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Octopus 3P: {e}")
        return error_return
