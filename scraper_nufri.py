
import re
from playwright.sync_api import sync_playwright

def obtener_texto_desplegado(nombre_tarifa):
    """Abre la web de Nufri, acepta cookies, hace clic en 'Ver precios' de la tarjeta deseada y extrae el texto."""
    url = "https://www.energianufri.com/es/tarifas-luz"
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
            
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2500)
            
            # Aceptar cookies automáticamente
            for texto_btn in ["Aceptar", "Permitir todas", "Aceptar y continuar", "Consentir"]:
                try:
                    boton = page.locator(f"button:has-text('{texto_btn}')")
                    if boton.count() > 0:
                        boton.first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        break
                except:
                    pass
            
            # Filtrar la tarjeta específica que contiene la tarifa y el botón 'Ver precios'
            tarjeta = page.locator("*").filter(has_text=nombre_tarifa).filter(has=page.locator("text=Ver precios")).last
            btn_ver = tarjeta.locator("text=Ver precios").first
            
            if btn_ver.count() > 0:
                btn_ver.click()
                page.wait_for_timeout(2000)
            
            texto = page.evaluate("document.body.innerText")
            browser.close()
            return texto
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Nufri ({nombre_tarifa}): {e}")
        return None

def obtener_precios_fijo():
    """Extrae los precios de la tarifa 'Universal sin horarios' (Fijo 24h) de Nufri"""
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_desplegado("Universal sin horarios")
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€?\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€?\s*/\s*kw', t_lower)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.50]
        precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if p != '']
        
        # Normalización de potencia (si viniese en anual o mensual, la convierte a diaria)
        potencias_diarias = []
        for p in precios_p_raw:
            if p > 1.5:
                if p > 15.0:
                    potencias_diarias.append(round(p / 365.0, 6))
                else:
                    potencias_diarias.append(round(p / 30.0, 6))
            elif 0.0001 <= p <= 0.5:
                potencias_diarias.append(p)
                
        potencias_diarias = sorted(list(set(potencias_diarias)))
        
        if precios_e and potencias_diarias:
            p_val = potencias_diarias[0]
            p_punta = max(potencias_diarias) if len(potencias_diarias) > 1 else p_val
            p_valle = min(potencias_diarias) if len(potencias_diarias) > 1 else p_val
            
            return {
                "Precio_P_Punta": p_punta,
                "Precio_P_Valle": p_valle,
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron aislar los precios de Nufri Fijo.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Nufri Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae los precios de la tarifa 'Universal con horarios' (3 Periodos) de Nufri"""
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    texto = obtener_texto_desplegado("Universal con horarios")
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€?\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€?\s*/\s*kw', t_lower)
        
        precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
        precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if p != '']
        
        potencias_diarias = []
        for p in precios_p_raw:
            if p > 1.5:
                if p > 15.0:
                    potencias_diarias.append(round(p / 365.0, 6))
                else:
                    potencias_diarias.append(round(p / 30.0, 6))
            elif 0.0001 <= p <= 0.5:
                potencias_diarias.append(p)
                
        potencias_diarias = sorted(list(set(potencias_diarias)))
        
        precios_e_unicos = []
        for p in precios_e_raw:
            if not precios_e_unicos or precios_e_unicos[-1] != p:
                precios_e_unicos.append(p)
                
        if len(precios_e_unicos) >= 3 and len(potencias_diarias) >= 1:
            e_sort = sorted(precios_e_unicos[:3])
            p_val = potencias_diarias[0]
            p_punta = max(potencias_diarias) if len(potencias_diarias) > 1 else p_val
            p_valle = min(potencias_diarias) if len(potencias_diarias) > 1 else p_val
            
            return {
                "Precio_P_Punta": p_punta,
                "Precio_P_Valle": p_valle,
                "Precio_E_Punta": e_sort[-1],
                "Precio_E_Llano": e_sort[1],
                "Precio_E_Valle": e_sort[0]
            }

        print("⚠️ No se pudieron aislar los precios de Nufri 3P.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Nufri 3P: {e}")
        return error_return
