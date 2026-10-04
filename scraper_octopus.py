import re
from playwright.sync_api import sync_playwright

def obtener_texto_visible(url):
    """Abre la web y extrae únicamente el texto visible (innerText) tal y como lo ve el usuario, sin código HTML."""
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
            
            # Cargar la página y esperar a que la red esté inactiva
            page.goto(url, wait_until="networkidle", timeout=40000)
            page.wait_for_timeout(2000) # Breve espera extra para renderizado final
            
            # Extraer el texto visual puro
            texto = page.evaluate("document.body.innerText")
            browser.close()
            return texto
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Octopus: {e}")
        return None

def obtener_precios_fijo():
    """Extrae los precios de la tarifa 'Octopus Relax' (Fija 24h)"""
    url = "https://octopusenergy.es/precios"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto_visible = obtener_texto_visible(url)
    if not texto_visible:
        return error_return

    try:
        texto_limpio = texto_visible.lower()
        
        # Aislar exclusivamente la columna de "Octopus Relax"
        idx_relax = texto_limpio.find("octopus relax")
        idx_flexi = texto_limpio.find("octopus flexi")
        
        if idx_relax == -1:
            print("⚠️ No se encontró la columna 'Octopus Relax'.")
            return error_return
            
        bloque = texto_limpio[idx_relax:idx_flexi] if idx_flexi != -1 else texto_limpio[idx_relax:idx_relax+1000]
        
        # Buscar el precio de energía (€/kWh)
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', bloque)
        
        # Buscar los precios de potencia mensual (€/kW/mes) 
        # La regex se detiene en kW, por lo que captura el número sin importar si detrás pone 'mes'
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', bloque)
        
        if matches_energia and len(matches_potencia) >= 2:
            precio_e = float(matches_energia[0].replace(',', '.'))
            
            # En la web visualmente aparecen dos potencias (Punta y Valle)
            p_punta_mes = float(matches_potencia[0].replace(',', '.'))
            p_valle_mes = float(matches_potencia[1].replace(',', '.'))
            
            # Conversión a diario: dividimos entre 30 (La web indica explícitamente "*Precio calculado para 30 días")
            return {
                "Precio_P_Punta": round(p_punta_mes / 30, 6),
                "Precio_P_Valle": round(p_valle_mes / 30, 6),
                "Precio_E_Fijo": precio_e
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
    
    texto_visible = obtener_texto_visible(url)
    if not texto_visible:
        return error_return

    try:
        texto_limpio = texto_visible.lower()
        
        # Aislar exclusivamente la columna de "Octopus 3"
        idx_3p = texto_limpio.find("octopus 3")
        idx_relax = texto_limpio.find("octopus relax")
        
        if idx_3p == -1:
            print("⚠️ No se encontró la columna 'Octopus 3'.")
            return error_return
            
        bloque = texto_limpio[idx_3p:idx_relax] if idx_relax != -1 else texto_limpio[idx_3p:idx_3p+1000]
        
        matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', bloque)
        matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', bloque)
        
        if len(matches_energia) >= 3 and len(matches_potencia) >= 2:
            # Orden visual secuencial idéntico a la web: Punta (P1), Llano (P2), Valle (P3)
            e_punta = float(matches_energia[0].replace(',', '.'))
            e_llano = float(matches_energia[1].replace(',', '.'))
            e_valle = float(matches_energia[2].replace(',', '.'))
            
            # Orden visual secuencial: Punta (P1) mensual, Valle (P2) mensual
            p_punta_mes = float(matches_potencia[0].replace(',', '.'))
            p_valle_mes = float(matches_potencia[1].replace(',', '.'))
            
            # Devolvemos aplicando la división por 30 días para compatibilidad global
            return {
                "Precio_P_Punta": round(p_punta_mes / 30, 6),
                "Precio_P_Valle": round(p_valle_mes / 30, 6),
                "Precio_E_Punta": e_punta,
                "Precio_E_Llano": e_llano,
                "Precio_E_Valle": e_valle
            }
            
        print("⚠️ No se pudieron extraer valores numéricos completos de Octopus 3.")
        return error_return
        
    except Exception as e:
        print(f"⚠️ Excepción en Octopus 3P: {e}")
        return error_return
