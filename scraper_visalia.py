import re
from playwright.sync_api import sync_playwright

def obtener_texto_visible(url):
    """Abre la web de Visalia con Playwright y extrae el texto visible puro."""
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
            page.wait_for_timeout(2500)
            
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
        print(f"⚠️ Error al renderizar navegador en Visalia ({url}): {e}")
        return None

def obtener_precios_fijo():
    """Extrae los precios de la tarifa Luz Fijo 24h de Visalia"""
    url = "https://visalia.es/luz/fijo24horas/"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_visible(url)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw\s*d[ií]a', t_lower)
        if not matches_potencia:
            matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
            
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.50]
        precios_p = [float(p.replace(',', '.')) for p in matches_potencia if 0.0001 <= float(p.replace(',', '.')) <= 0.50]
        
        if precios_e and precios_p:
            p_valor = precios_p[0]
            p_punta = max(precios_p) if len(precios_p) > 1 else p_valor
            p_valle = min(precios_p) if len(precios_p) > 1 else p_valor
            
            return {
                "Precio_P_Punta": p_punta,
                "Precio_P_Valle": p_valle,
                "Precio_E_Fijo": precios_e[0]
            }

        print("⚠️ No se pudieron aislar los precios de Visalia Fijo.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Visalia Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae los precios de la tarifa Luz 3 Periodos de Visalia"""
    url = "https://visalia.es/luz/luz-3-periodos/"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    texto = obtener_texto_visible(url)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        # Extraer usando las etiquetas explícitas que muestra Visalia en las tarjetas
        match_e_valle = re.search(r'valle[^\d]*(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        match_e_llano = re.search(r'llano[^\d]*(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        match_e_punta = re.search(r'punta[^\d]*(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        
        match_p_valle = re.search(r'valle[^\d]*(\d+[,\.]\d+)\s*€\s*/\s*kw\s*d[ií]a', t_lower)
        match_p_punta = re.search(r'punta[^\d]*(\d+[,\.]\d+)\s*€\s*/\s*kw\s*d[ií]a', t_lower)
        
        if match_e_valle and match_e_llano and match_e_punta and match_p_valle and match_p_punta:
            return {
                "Precio_P_Punta": float(match_p_punta.group(1).replace(',', '.')),
                "Precio_P_Valle": float(match_p_valle.group(1).replace(',', '.')),
                "Precio_E_Punta": float(match_e_punta.group(1).replace(',', '.')),
                "Precio_E_Llano": float(match_e_llano.group(1).replace(',', '.')),
                "Precio_E_Valle": float(match_e_valle.group(1).replace(',', '.'))
            }
            
        # Respaldo por listas secuenciales
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
        
        precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
        precios_p = [float(p.replace(',', '.')) for p in matches_potencia if 0.0001 <= float(p.replace(',', '.')) <= 0.50]
        
        if len(precios_e) >= 3 and len(precios_p) >= 2:
            e_sort = sorted(precios_e)
            p_sort = sorted(precios_p)
            return {
                "Precio_P_Punta": p_sort[-1],
                "Precio_P_Valle": p_sort[0],
                "Precio_E_Punta": e_sort[-1],
                "Precio_E_Llano": e_sort[len(e_sort)//2],
                "Precio_E_Valle": e_sort[0]
            }

        print("⚠️ No se pudieron aislar los precios de Visalia 3P.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Visalia 3P: {e}")
        return error_return
