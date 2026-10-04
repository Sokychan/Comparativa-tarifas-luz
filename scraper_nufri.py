import re
from playwright.sync_api import sync_playwright

def obtener_texto_modal(nombre_tarifa):
    """Abre la web, hace clic quirúrgico en la tarjeta usando JS y extrae ÚNICAMENTE el texto del modal."""
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
            page.wait_for_timeout(3000)
            
            # Aceptar cookies mediante JavaScript
            page.evaluate("""
                const btns = Array.from(document.querySelectorAll('button, a'));
                const cookieBtn = btns.find(b => /aceptar|permitir|consentir/i.test(b.innerText));
                if(cookieBtn) cookieBtn.click();
            """)
            page.wait_for_timeout(1000)
            
            # Clic exacto en 'Ver precios' de la tarjeta específica
            js_click = f"""
            () => {{
                const tarName = '{nombre_tarifa}';
                const allElements = Array.from(document.querySelectorAll('*'));
                // Buscar el texto exacto del título de la tarifa
                const headings = allElements.filter(el => 
                    el.children.length === 0 && 
                    el.textContent.trim().toLowerCase() === tarName.toLowerCase()
                );
                
                if (headings.length > 0) {{
                    let card = headings[headings.length - 1];
                    // Subir por el DOM hasta encontrar el contenedor que tenga el botón 'Ver precios'
                    while(card && card.tagName !== 'BODY') {{
                        const btns = Array.from(card.querySelectorAll('button, a')).filter(b => b.textContent.toLowerCase().includes('ver precios'));
                        if (btns.length > 0) {{
                            btns[0].click();
                            return true;
                        }}
                        card = card.parentElement;
                    }}
                }}
                return false;
            }}
            """
            page.evaluate(js_click)
            page.wait_for_timeout(2500)
            
            # EXTRAER SOLO EL MODAL: Esto evita capturar los precios gigantes de la página principal
            texto_modal = page.evaluate("""
            () => {
                const dialog = document.querySelector('[role="dialog"], [data-state="open"]');
                return dialog ? dialog.innerText : '';
            }
            """)
            
            browser.close()
            # Limpieza de saltos de línea y tabulaciones
            return ' '.join(texto_modal.split()).lower() if texto_modal else ""
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Nufri ({nombre_tarifa}): {e}")
        return ""

def extraer_precios_limpios(texto_limpio):
    """Extrae y clasifica los precios mediante expresiones regulares estrictas."""
    matches_energia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w\s*h', texto_limpio)
    # Excluye /kWh para capturar solo la potencia
    matches_potencia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w(?!\s*h)', texto_limpio)
    
    # Filtro de seguridad (Energía: 0.08 a 0.40)
    precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.08 <= float(p.replace(',', '.')) <= 0.40]
    precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if p != '']
    
    # Respaldo si falla la extracción por unidades
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
