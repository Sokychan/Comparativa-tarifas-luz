import re
from playwright.sync_api import sync_playwright

def obtener_texto_visible(url):
    """Abre la web de EnergyaVM con Playwright y extrae el texto visible puro."""
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
            page.wait_for_timeout(2000)
            
            # Aceptar cookies automáticamente si aparece el aviso
            for texto_btn in ["Aceptar", "Permitir todas", "Aceptar y continuar", "Consentir"]:
                try:
                    boton = page.locator(f"button:has-text('{texto_btn}')")
                    if boton.count() > 0:
                        boton.first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        break
                except:
                    pass
            
            texto = page.evaluate("document.body.innerText")
            browser.close()
            return texto
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en EnergyaVM ({url}): {e}")
        return None

def obtener_precios_fijo():
    """Extrae los precios de la Tarifa Fija 24h de EnergyaVM"""
    url = "https://www.energyavm.es/luz/formula-fija-24-horas-luz/"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_visible(url)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.50]
        precios_p = sorted(list(set([float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.50])))
        
        if precios_e and len(precios_p) >= 2:
            return {
                "Precio_P_Punta": precios_p[-1],
                "Precio_P_Valle": precios_p[0],
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron aislar los precios de EnergyaVM Fijo.")
        return error_return
            
    except Exception as e:
        print(f"⚠️️ Excepción en EnergyaVM Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae los precios de la Tarifa 3 Periodos de EnergyaVM de forma flexible"""
    url = "https://www.energyavm.es/luz/formula-fija-3-periodos-luz/"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    texto = obtener_texto_visible(url)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
        
        precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
        precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.50]
        
        print(f"🔍 [DEBUG] EnergyaVM 3P - Energías detectadas: {precios_e_raw}, Potencias: {precios_p_raw}")
        
        precios_e_unicos = []
        for p in precios_e_raw:
            if not precios_e_unicos or precios_e_unicos[-1] != p:
                precios_e_unicos.append(p)
                
        precios_p = sorted(list(set(precios_p_raw)))
        
        # Condición estándar
        if len(precios_e_unicos) >= 3 and len(precios_p) >= 2:
            precios_e_ordenados = sorted(precios_e_unicos[:3])
            return {
                "Precio_P_Punta": precios_p[-1],
                "Precio_P_Valle": precios_p[0],
                "Precio_E_Punta": precios_e_ordenados[-1],
                "Precio_E_Llano": precios_e_ordenados[1],
                "Precio_E_Valle": precios_e_ordenados[0]
            }
        # Condición de emergencia (si encuentra al menos 1 o 2 valores pero la web los estructura distinto)
        elif len(precios_e_unicos) >= 1 and len(precios_p) >= 1:
            e_sort = sorted(precios_e_unicos)
            valle = e_sort[0]
            punta = e_sort[-1]
            llano = e_sort[len(e_sort)//2] if len(e_sort) > 1 else valle
            return {
                "Precio_P_Punta": precios_p[-1] if precios_p else 0.1,
                "Precio_P_Valle": precios_p[0] if precios_p else 0.02,
                "Precio_E_Punta": punta,
                "Precio_E_Llano": llano,
                "Precio_E_Valle": valle
            }

        print("⚠️ No se pudieron aislar los precios de EnergyaVM 3P.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en EnergyaVM 3P: {e}")
        return error_return
