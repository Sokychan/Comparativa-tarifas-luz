import re
from playwright.sync_api import sync_playwright

def obtener_texto_y_numeros(nombre_tarifa):
    """Abre la web, usa JavaScript para hacer clic en la tarjeta exacta y extrae únicamente el texto del modal."""
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
            
            # Aceptar cookies mediante JS
            page.evaluate("""
                const btns = Array.from(document.querySelectorAll('button, a'));
                const cookieBtn = btns.find(b => /aceptar|permitir|consentir/i.test(b.innerText));
                if(cookieBtn) cookieBtn.click();
            """)
            page.wait_for_timeout(1000)
            
            # Clic quirúrgico en 'Ver precios' de la tarjeta deseada usando JS
            page.evaluate(f"""
                const keyword = '{nombre_tarifa.lower()}';
                const containers = Array.from(document.querySelectorAll('div, section, article'));
                
                const validCards = containers.filter(el => 
                    el.innerText.toLowerCase().includes(keyword) && 
                    el.innerText.toLowerCase().includes('ver precios')
                );
                
                if(validCards.length > 0) {{
                    validCards.sort((a, b) => a.innerText.length - b.innerText.length);
                    const card = validCards[0];
                    const btn = Array.from(card.querySelectorAll('button, a')).find(b => b.innerText.toLowerCase().includes('ver precios'));
                    if(btn) btn.click();
                }}
            """)
            page.wait_for_timeout(2500)
            
            # Aislar únicamente el texto dentro del cuadro modal emergente si está abierto
            texto_modal = page.evaluate("""() => {
                const modal = document.querySelector("[role='dialog'], [data-state='open'], .sheet-content");
                if (modal && modal.innerText.length > 20) {
                    return modal.innerText;
                }
                return document.body.innerText;
            }""")
            
            browser.close()
            return ' '.join(texto_modal.split()).lower()
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Nufri ({nombre_tarifa}): {e}")
        return ""

def extraer_precios_limpios(texto_limpio):
    """Extrae y clasifica los precios de energía y potencia dentro de rangos estrictos de mercado."""
    matches_energia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w\s*h', texto_limpio)
    matches_potencia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w(?!\s*h)', texto_limpio)
    
    # Ajuste de umbral: solo aceptamos energía entre 0.07 €/kWh y 0.50 €/kWh para descartar el 0.03 €
    precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.07 <= float(p.replace(',', '.')) <= 0.50]
    precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if p != '']
    
    if not precios_p_raw:
        todos_numeros = re.findall(r'(\d+[,\.]\d{2,6})', texto_limpio)
        for n in todos_numeros:
            try:
                val = float(n.replace(',', '.'))
                if (0.001 <= val <= 0.15) or (15.0 <= val <= 60.0):
                    precios_p_raw.append(val)
            except:
                pass

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
            
    return precios_e_unicos, potencias_diarias

def obtener_precios_fijo():
    """Extrae los precios de la tarifa 'Universal sin horarios' (Fijo 24h)"""
    error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    
    texto = obtener_texto_y_numeros("Universal sin horarios")
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
    """Extrae los precios de la tarifa 'Universal con horarios' (3 Periodos)"""
    error_return = {
        "Precio_P_Punta": 0, "Precio_P_Valle": 0, 
        "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0
    }
    
    texto = obtener_texto_y_numeros("Universal con horarios")
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
                "Precio_E_Punta": e_sort[-1], # El más alto
                "Precio_E_Llano": e_sort[1],  # El intermedio
                "Precio_E_Valle": e_sort[0]   # El más bajo
            }

        print("⚠️ No se pudieron aislar los precios de Nufri 3P.")
        return error_return
            
    except Exception as e:
        print(f"⚠️️ Excepción en Nufri 3P: {e}")
        return error_return
