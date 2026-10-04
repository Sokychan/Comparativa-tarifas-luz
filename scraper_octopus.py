import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Variable global para cachear la web y no abrir el navegador 2 veces
_html_cache = None

def obtener_html_con_navegador(url):
    global _html_cache
    if _html_cache:
        return _html_cache
        
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
                locale="es-ES",
                timezone_id="Europe/Madrid"
            )
            
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            page.goto(url, wait_until="networkidle", timeout=40000)
            page.wait_for_timeout(3000) # Espera de seguridad para carga dinámica
            
            html = page.content()
            browser.close()
            
            # Guardamos la página en la memoria global
            _html_cache = html
            return html
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Octopus: {e}")
        return None

def limpiar_html_agresivo(html_text):
    """Limpia el código web dejando solo texto plano continuado sin saltos de línea."""
    soup = BeautifulSoup(html_text, 'html.parser')
    # Eliminar scripts y estilos que puedan contener código basura
    for script in soup(["script", "style"]):
        script.extract()
        
    texto = soup.get_text(separator=' ')
    texto = texto.replace('&euro;', '€').replace('&#8364;', '€').replace('&nbsp;', ' ')
    return ' '.join(texto.split())

def obtener_precios_fijo():
    """Extrae la tarifa 'Octopus Relax' (Fija 24h)"""
    url = "https://octopusenergy.es/precios"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    html = obtener_html_con_navegador(url)
    if not html: return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html)
        
        # Patrón exacto: Busca "Octopus Relax" -> [Energía] -> [Potencia Punta] -> [Potencia Valle]
        patron = r'Octopus Relax.{1,300}?(\d+[,\.]\d+)\s*€.*?kWh.{1,300}?(\d+[,\.]\d+)\s*€.*?kW.{1,100}?(\d+[,\.]\d+)\s*€.*?kW'
        match = re.search(patron, texto_limpio, re.IGNORECASE)
        
        if match:
            e_fijo = float(match.group(1).replace(',', '.'))
            p_punta_mes = float(match.group(2).replace(',', '.'))
            p_valle_mes = float(match.group(3).replace(',', '.'))
            
            # Conversión de €/kW/mes a €/kW/día
            return {
                "Precio_P_Punta": round(p_punta_mes / 30, 6),
                "Precio_P_Valle": round(p_valle_mes / 30, 6),
                "Precio_E_Fijo": e_fijo
            }
            
        print("⚠️ No se encontró la secuencia correcta de precios para Octopus Relax.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Octopus Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae la tarifa 'Octopus 3' (3 Periodos)"""
    url = "https://octopusenergy.es/precios"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0}
    
    html = obtener_html_con_navegador(url)
    if not html: return error_return

    try:
        texto_limpio = limpiar_html_agresivo(html)
        
        # Patrón exacto: Busca "Octopus 3" -> E.P1 -> E.P2 -> E.P3 -> P.P1 -> P.P2
        patron = r'Octopus 3.{1,300}?(\d+[,\.]\d+)\s*€.*?kWh.{1,100}?(\d+[,\.]\d+)\s*€.*?kWh.{1,100}?(\d+[,\.]\d+)\s*€.*?kWh.{1,300}?(\d+[,\.]\d+)\s*€.*?kW.{1,100}?(\d+[,\.]\d+)\s*€.*?kW'
        match = re.search(patron, texto_limpio, re.IGNORECASE)
        
        if match:
            e_punta = float(match.group(1).replace(',', '.'))
            e_llano = float(match.group(2).replace(',', '.'))
            e_valle = float(match.group(3).replace(',', '.'))
            p_punta_mes = float(match.group(4).replace(',', '.'))
            p_valle_mes = float(match.group(5).replace(',', '.'))
            
            # Conversión de €/kW/mes a €/kW/día
            return {
                "Precio_P_Punta": round(p_punta_mes / 30, 6),
                "Precio_P_Valle": round(p_valle_mes / 30, 6),
                "Precio_E_Punta": e_punta,
                "Precio_E_Llano": e_llano,
                "Precio_E_Valle": e_valle
            }
            
        print("⚠️ No se encontró la secuencia correcta de precios para Octopus 3.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Octopus 3P: {e}")
        return error_return
