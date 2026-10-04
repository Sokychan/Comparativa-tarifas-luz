import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def obtener_html_con_navegador(url):
    """Abre la web de Iberdrola usando Playwright con huella digital humana para evitar bloqueos WAF."""
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
            page.wait_for_timeout(3000) # Espera de seguridad para el DOM de Iberdrola
            
            content = page.content()
            browser.close()
            return content
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Iberdrola ({url}): {e}")
        return None

def limpiar_html_agresivo(html_text):
    """Limpia el código web extrayendo el texto plano con BeautifulSoup."""
    soup = BeautifulSoup(html_text, 'html.parser')
    for script in soup(["script", "style"]):
        script.extract()
        
    texto = soup.get_text(separator=' ')
    texto = texto.replace('&euro;', '€').replace('&#8364;', '€').replace('&nbsp;', ' ')
    return ' '.join(texto.split())

def obtener_precios_fijo():
    """Extrae los precios del Plan Online (Precio Fijo 24h) de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    html = obtener_html_con_navegador(url)
    if not html:
        return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html)
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW', texto_limpio, re.IGNORECASE)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.05 <= float(p.replace(',', '.')) <= 0.40]
        precios_p = sorted(list(set([float(p.replace(',', '.')) for p in matches_potencia if 0.01 <= float(p.replace(',', '.')) <= 0.30])))
        
        if precios_e and len(precios_p) >= 2:
            return {
                "Precio_P_Punta": precios_p[-1], # El más alto
                "Precio_P_Valle": precios_p[0],  # El más bajo
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron filtrar los valores numéricos de Iberdrola Fijo.")
        return error_return
            
    except Exception as e:
        print(f"⚠️️ Excepción en Iberdrola Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae los precios del Plan Online 3 Periodos de Iberdrola"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    html = obtener_html_con_navegador(url)
    if not html:
        return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html)
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW', texto_limpio, re.IGNORECASE)
        
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

        print("⚠️ No se pudieron filtrar los precios de Iberdrola 3P.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Iberdrola 3P: {e}")
        return error_return
