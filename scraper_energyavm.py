import re
from playwright.sync_api import sync_playwright

def obtener_texto_pagina(url):
    """Abre la web de EnergyaVM y extrae el texto visible puro."""
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
        print(f"⚠️ Error al renderizar navegador en EnergyaVM ({url}): {e}")
        return None

def obtener_precios_fijo():
    """Extrae con precisión los precios de la Tarifa Fija 24h de EnergyaVM"""
    url = "https://www.energyavm.es/luz/formula-fija-24-horas-luz/"
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_pagina(url)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        # Anclaje estricto a P1 y P2 del término de potencia (anuales -> conversión a diarios /365)
        p1_m = re.search(r'p1[^\d]*(\d+[\.,]\d+)', t_lower)
        p2_m = re.search(r'p2[^\d]*(\d+[\.,]\d+)', t_lower)
        
        # Anclaje estricto al término de energía fijo
        e_m = re.search(r'término de energía[^\d]*(\d+[\.,]\d+)', t_lower)
        
        if p1_m and p2_m and e_m:
            p1 = float(p1_m.group(1).replace(',', '.')) / 365.0
            p2 = float(p2_m.group(1).replace(',', '.')) / 365.0
            ef = float(e_m.group(1).replace(',', '.'))
            
            return {
                "Precio_P_Punta": round(p1, 6),
                "Precio_P_Valle": round(p2, 6),
                "Precio_E_Fijo": ef
            }

        print("⚠️ No se pudieron aislar los precios de EnergyaVM Fijo.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en EnergyaVM Fijo: {e}")
        return error_return

def obtener_precios_3p():
    """Extrae con precisión los precios de la Tarifa 3 Periodos de EnergyaVM"""
    url = "https://www.energyavm.es/luz/formula-fija-3-periodos-luz/"
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    texto = obtener_texto_pagina(url)
    if not texto:
        return error_return

    try:
        t_lower = texto.lower()
        
        # Potencias P1 y P2
        p1_m = re.search(r'p1[^\d]*(\d+[\.,]\d+)', t_lower)
        p2_m = re.search(r'p2[^\d]*(\d+[\.,]\d+)', t_lower)
        
        # Aislar la sección de energía para capturar P1, P2 y P3 específicos
        idx_e = t_lower.find("término de energía")
        seccion_energia = t_lower[idx_e:] if idx_e != -1 else t_lower
        
        e_valores = re.findall(r'p([123])[^\d]*(\d+[\.,]\d+)', seccion_energia)
        
        energias = {}
        for p, val in e_valores:
            energias[int(p)] = float(val.replace(',', '.'))
            
        if p1_m and p2_m and len(energias) >= 3:
            p1 = float(p1_m.group(1).replace(',', '.')) / 365.0
            p2 = float(p2_m.group(1).replace(',', '.')) / 365.0
            
            return {
                "Precio_P_Punta": round(p1, 6),
                "Precio_P_Valle": round(p2, 6),
                "Precio_E_Punta": energias.get(1, 0),
                "Precio_E_Llano": energias.get(2, 0),
                "Precio_E_Valle": energias.get(3, 0)
            }

        print("⚠️ No se pudieron aislar los precios de EnergyaVM 3P.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en EnergyaVM 3P: {e}")
        return error_return
