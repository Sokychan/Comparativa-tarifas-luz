import json
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def extraer_datos_agresivos(url):
    """Método agresivo que extrae y recompone todos los precios válidos de la página."""
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
            
            page.goto(url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(3000)
            
            # Auto-aceptar cookies de forma contundente
            for texto_btn in ["Aceptar", "Permitir todas", "Aceptar y continuar", "Consentir", "Continuar"]:
                try:
                    boton = page.locator(f"button:has-text('{texto_btn}')")
                    if boton.count() > 0:
                        boton.first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        break
                except:
                    pass
            
            html_content = page.content()
            browser.close()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Eliminar scripts y estilos basura
            for s in soup(["script", "style", "noscript"]):
                s.extract()
                
            # TRUCO CLAVE: separator='' une todo el texto sin espacios, recomponiendo números partidos
            texto_crudo = soup.get_text(separator='')
            
            # Normalizar caracteres y símbolos monetarios
            texto_limpio = texto_crudo.replace('&euro;', '€').replace('&#8364;', '€').replace('€', ' € ')
            
            # Buscar todos los patrones numéricos con decimales seguidos de € o unidades de luz
            # Captura formatos como 0,1499 o 0.1499
            matches = re.findall(r'(\d+[,\.]\d+)\s*(?:€|\/kWh|\/kW)', texto_limpio, re.IGNORECASE)
            
            if not matches:
                # Búsqueda libre secundaria si no encuentra etiquetas de moneda exactas
                matches = re.findall(r'(\d+,\d{2,4})', texto_limpio)
                
            # Convertir a float y filtrar rangos lógicos del mercado eléctrico español
            valores_validos = []
            for m in matches:
                try:
                    val = float(m.replace(',', '.'))
                    # Rango válido para energía (0.03 a 0.50 €/kWh) y potencia (0.005 a 0.30 €/kW día)
                    if 0.005 <= val <= 0.60:
                        if val not in valores_validos:
                            valores_validos.append(val)
                except:
                    pass
                    
            return sorted(valores_validos)
            
    except Exception as e:
        print(f"⚠️ Error en método agresivo para {url}: {e}")
        return []

def obtener_precios_fijo():
    """Extrae los precios del Plan Online (Precio Fijo 24h) de Iberdrola de forma agresiva"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    precios = extraer_datos_agresivos(url)
    print(f"🔍 [DEBUG] Precios detectados en Fijo: {precios}")
    
    # Filtramos valores lógicos encontrados en la página
    # Iberdrola fijo suele tener energía sobre 0.10-0.20 y potencia en dos tramos
    energias = [p for p in precios if 0.08 <= p <= 0.35]
    potencias = [p for p in precios if 0.005 <= p <= 0.20]
    
    if energias and len(potencias) >= 2:
        return {
            "Precio_P_Punta": max(potencias),
            "Precio_P_Valle": min(potencias),
            "Precio_E_Fijo": energias[0]
        }
        
    print("⚠️ No se pudieron consolidar los precios de Iberdrola Fijo.")
    return error_return

def obtener_precios_3p():
    """Extrae los precios del Plan Online 3 Periodos de Iberdrola de forma agresiva"""
    url = "https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    precios = extraer_datos_agresivos(url)
    print(f"🔍 [DEBUG] Precios detectados en 3P: {precios}")
    
    energias = sorted([p for p in precios if 0.05 <= p <= 0.45])
    potencias = [p for p in precios if 0.005 <= p <= 0.20]
    
    if len(energias) >= 3 and len(potencias) >= 2:
        return {
            "Precio_P_Punta": max(potencias),
            "Precio_P_Valle": min(potencias),
            "Precio_E_Punta": energias[-1],
            "Precio_E_Llano": energias[1] if len(energias) > 1 else energias[0],
            "Precio_E_Valle": energias[0]
        }
        
    print("⚠️ No se pudieron consolidar los precios de Iberdrola 3P.")
    return error_return
