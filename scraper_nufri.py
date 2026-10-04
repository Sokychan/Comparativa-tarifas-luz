import re
from playwright.sync_api import sync_playwright

def obtener_texto_modal(nombre_tarifa):
    """Localiza la tarjeta tolerando saltos de línea, pulsa 'Ver precios' y extrae el modal."""
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
            
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            
            # Aceptar cookies
            page.evaluate("""
                const btns = Array.from(document.querySelectorAll('button, a'));
                const cookieBtn = btns.find(b => /aceptar|permitir|consentir/i.test(b.innerText));
                if(cookieBtn) cookieBtn.click();
            """)
            page.wait_for_timeout(1000)
            
            # 1. Estrategia Playwright: Reemplazar espacios por .*? para tolerar saltos HTML ocultos
            regex_tarifa = nombre_tarifa.replace(" ", ".*?")
            
            # Buscar el contenedor más profundo (.last) que tenga el nombre y el botón 'Ver precios'
            tarjetas = page.locator("div, article, section").filter(has_text=re.compile(regex_tarifa, re.IGNORECASE)).filter(has=page.locator("button, a", has_text=re.compile("ver precios", re.IGNORECASE)))
            
            if tarjetas.count() > 0:
                btn = tarjetas.last.locator("button, a").filter(has_text=re.compile("ver precios", re.IGNORECASE)).first
                btn.click(force=True)
                page.wait_for_timeout(2500)
                
            # Identificar la ventana modal abierta
            modal = page.locator("[role='dialog'], [data-state='open'], div[id*='radix']").first
            
            # 2. Estrategia Respaldo: Si el modal no se abrió, usar índice estático de la cuadrícula
            if modal.count() == 0 or not modal.is_visible():
                idx = 4 if "sin horarios" in nombre_tarifa.lower() else 3
                page.evaluate(f"""
                    const btns = Array.from(document.querySelectorAll('button, a')).filter(b => b.innerText.toLowerCase().includes('ver precios'));
                    if(btns.length > {idx}) btns[{idx}].click();
                """)
                page.wait_for_timeout(2500)
            
            if modal.count() > 0 and modal.is_visible():
                texto_modal = modal.inner_text()
            else:
                texto_modal = ""
                
            browser.close()
            return ' '.join(texto_modal.split()).lower() if texto_modal else ""
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Nufri ({nombre_tarifa}): {e}")
        return ""

def extraer_precios_limpios(texto_limpio):
    """Extrae y clasifica los precios mediante expresiones regulares estrictas."""
    matches_energia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w\s*h', texto_limpio)
    # Excluye /kWh para capturar solo la potencia
    matches_potencia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w(?!\s*h)', texto_limpio)
    
    # Filtro de mercado (Energía: 0.08 a 0.40)
    precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.08 <= float(p.replace(',', '.')) <= 0.40]
    precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if p != '']
    
    # Respaldo de emergencia si no detecta las unidades correctamente
    if not precios_e_raw or not precios_p_raw:
        todos_numeros = re.findall(r'(\d+[,\.]\d{2,6})', texto_limpio)
        candidatos = []
        for n in todos_numeros:
            try:
                candidatos.append(float(n.replace(',', '.')))
            except:
                pass
                
        if not precios_e_raw:
            precios_e_raw = [c for c in candidatos if 0.08 <= c <= 0.40]
        if not precios_p_raw:
            precios_p_raw = [c for c in candidatos if (0.01 <= c <= 0.15) or (15.0 <= c <= 60.0)]

    # Conversión de potencia (anual a diaria si supera los 15€)
    potencias_diarias = []
    for p in precios_p_raw:
        if p > 15.0:
            potencias_diarias.append(round(p / 365.0, 6))
        elif 0.0001 <= p <= 0.5:
            potencias_diarias.append(p)
            
    potencias_diarias = sorted(list(set(potencias_diarias)))
    
    precios_e_unicos = []
    for p in precios_e_raw:
        if not precios_e_unicos or precios_e_unicos[-1] != p:
            precios_e_unicos.append(p)
            
    return sorted(precios_e_unicos), potencias_diarias

def obtener_precios_fijo():
    """Extrae los precios de la tarifa 'Universal sin horarios' (Fijo 24h) de Nufri"""
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_modal("Universal sin horarios")
    if not texto: return error_return

    try:
        precios_e, potencias_p = extraer_precios_limpios(texto)
        print(f"🔍 [DEBUG] Nufri Fijo - Energías: {precios_e}, Potencias: {potencias_p}")
        
        if precios_e and potencias_p:
            p_val = potencias_p[0]
            p_punta = max(potencias_p) if len(potencias_p) > 1 else p_val
            p_valle = min(potencias_p) if len(potencias_p) > 1 else p_val
            
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
    
    texto = obtener_texto_modal("Universal con horarios")
    if not texto: return error_return

    try:
        precios_e, potencias_p = extraer_precios_limpios(texto)
        print(f"🔍 [DEBUG] Nufri 3P - Energías: {precios_e}, Potencias: {potencias_p}")
        
        if len(precios_e) >= 3 and potencias_p:
            e_sort = sorted(precios_e[:3])
            p_val = potencias_p[0]
            p_punta = max(potencias_p) if len(potencias_p) > 1 else p_val
            p_valle = min(potencias_p) if len(potencias_p) > 1 else p_val
            
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
