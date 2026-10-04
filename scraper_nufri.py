import re
from playwright.sync_api import sync_playwright

def obtener_texto_modal(nombre_tarifa):
    """Inyecta JavaScript directo para saltarse los bloqueos de interfaz, forzar el clic y extraer el modal."""
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
            
            # networkidle asegura que todos los elementos interactivos hayan cargado en segundo plano
            page.goto(url, wait_until="networkidle", timeout=45000)
            
            # 1. Aceptar cookies agresivamente con JS
            page.evaluate("""
                const btns = Array.from(document.querySelectorAll('button, a'));
                const cookieBtn = btns.find(b => /aceptar|permitir|consentir/i.test(b.innerText));
                if(cookieBtn) cookieBtn.click();
            """)
            page.wait_for_timeout(1000)
            
            # 2. Navegación DOM directa mediante JS para forzar el clic en el botón correcto
            js_click = f"""
            () => {{
                let clicked = false;
                const tarName = '{nombre_tarifa}'.toLowerCase();
                
                // Buscar el texto exacto en cualquier elemento de texto puro
                const texts = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, p, span, div')).filter(el => 
                    el.children.length === 0 && el.textContent.toLowerCase().trim() === tarName
                );
                
                // Escalar hacia el padre hasta encontrar el botón de 'Ver precios'
                for (let el of texts) {{
                    let parent = el.parentElement;
                    while (parent && parent.tagName !== 'BODY') {{
                        const btns = Array.from(parent.querySelectorAll('button, a')).filter(b => /ver precios/i.test(b.textContent));
                        if (btns.length > 0) {{
                            btns[0].click();
                            clicked = true;
                            break;
                        }}
                        parent = parent.parentElement;
                    }}
                    if (clicked) break;
                }}
                
                // Respaldo de emergencia: si el texto cambió, clicamos por orden de aparición
                if (!clicked) {{
                    const allBtns = Array.from(document.querySelectorAll('button, a')).filter(b => /ver precios/i.test(b.textContent));
                    const idx = tarName.includes('sin horarios') ? 4 : 3;
                    if (allBtns.length > idx) {{
                        allBtns[idx].click();
                    }}
                }}
            }}
            """
            page.evaluate(js_click)
            
            # Damos 3 segundos completos para que la ventana emergente aparezca y cargue los datos
            page.wait_for_timeout(3000)
            
            # 3. Extraer estrictamente el modal
            texto_modal = page.evaluate("""
            () => {
                const modal = document.querySelector('[role="dialog"], [data-state="open"], div.fixed.z-50');
                if (modal && modal.innerText && modal.innerText.trim().length > 10) {
                    return modal.innerText;
                }
                return document.body.innerText; 
            }
            """)
            
            browser.close()
            return ' '.join(texto_modal.split()).lower() if texto_modal else ""
            
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en Nufri ({nombre_tarifa}): {e}")
        return ""

def extraer_precios_limpios(texto_limpio):
    """Extrae y clasifica los precios mediante expresiones regulares estrictas."""
    matches_energia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w\s*h', texto_limpio)
    matches_potencia = re.findall(r'(\d+[,\.]\d{2,6})\s*(?:€|eur)?\s*/?\s*k\s*w(?!\s*h)', texto_limpio)
    
    # Rango de mercado para energía: 0.08 a 0.40 €/kWh
    precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.08 <= float(p.replace(',', '.')) <= 0.40]
    precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if p != '']
    
    # Respaldo si no detecta las unidades correctamente
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
        print(f"🔍 [DEBUG] Nufri Fijo - Energías extraídas: {precios_e}, Potencias extraídas: {potencias_p}")
        
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
        print(f"🔍 [DEBUG] Nufri 3P - Energías extraídas: {precios_e}, Potencias extraídas: {potencias_p}")
        
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

        print("⚠️️ No se pudieron aislar los precios de Nufri 3P.")
        return error_return
            
    except Exception as e:
        print(f"⚠️ Excepción en Nufri 3P: {e}")
        return error_return
