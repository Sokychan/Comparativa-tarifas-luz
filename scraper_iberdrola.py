import re
from playwright.sync_api import sync_playwright

_html_cache_fijo = None
_html_cache_3p = None

def obtener_texto_visible(url, es_3p=False):
    """Extrae el texto visible puro de la página utilizando Playwright para evitar bloqueos WAF."""
    global _html_cache_fijo, _html_cache_3p
    if es_3p and _html_cache_3p:
        return _html_cache_3p
    if not es_3p and _html_cache_fijo:
        return _html_cache_fijo

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-web-security"
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
            
            page.goto(url, wait_until="networkidle", timeout=40000)
            page.wait_for_timeout(3000) # Espera de seguridad para renderizado completo
            
            texto = page.evaluate("document.body.innerText")
            browser.close()
            
            if es_3p:
                _html_cache_3p = texto
            else:
                _html_cache_fijo = texto
                
            return texto
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Iberdrola ({url}): {e}")
        return None

def obtener_precios_fijo():
    """Extrae los precios del Plan Online (Precio Fijo 24h) de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_visible(url, es_3p=False)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.05 <= float(p.replace(',', '.')) <= 0.40]
        precios_p = sorted(list(set([float(p.replace(',', '.')) for p in matches_potencia if 0.01 <= float(p.replace(',', '.')) <= 0.30])))
        
        if precios_e and len(precios_p) >= 2:
            return {
                "Precio_P_Punta": precios_p[-1], # El más alto es Punta
                "Precio_P_Valle": precios_p[0],  # El más bajo es Valle
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron aislar los precios de Iberdrola Fijo.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae los precios del Plan Online 3 Periodos de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    texto = obtener_texto_visible(url, es_3p=True)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
        
        precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
        precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if 0.01 <= float(p.replace(',', '.')) <= 0.30]
        
        # Filtrar duplicados consecutivos
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
                "Precio_E_Llano": precios_e_ordenados[1],  # El intermedio
                "Precio_E_Valle": precios_e_ordenados[0]   # El más bajo
            }

        print("⚠️ No se pudieron aislar los precios de Iberdrola 3P.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola 3P: {e}")
        return error_return
