import json
import os
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def limpiar_html_agresivo(html_text):
    texto = html_text.replace('&euro;', '€').replace('&#8364;', '€').replace('&nbsp;', ' ')
    texto_sin_tags = re.sub(r'<[^>]+>', ' ', texto)
    return ' '.join(texto_sin_tags.split())

def obtener_html_con_navegador(url, click_selector=None):
    """Abre la web con Playwright. Permite hacer clic en un selector si es necesario."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
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
            
            if click_selector:
                try:
                    page.click(click_selector, timeout=5000)
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"⚠️ No se pudo hacer clic en {click_selector}: {e}")
            
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"⚠️ Error al renderizar navegador en {url}: {e}")
        return None

def extraer_precios_texto(texto_limpio, tipo_tarifa, conversion_potencia_mes=False):
    """
    Busca patrones de energía y potencia.
    conversion_potencia_mes: Si es True, asume que la potencia está en meses y la pasa a días (*12/365).
    """
    error_fijo = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    error_3p = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0}
    
    # Extraer todos los valores seguidos de €/kWh o €/kW
    matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kWh', texto_limpio, re.IGNORECASE)
    # Patrón flexible para potencia (mes, día, o sin especificar)
    matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kW', texto_limpio, re.IGNORECASE)
    
    # Filtrar y limpiar valores numéricos realistas
    precios_e = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.60]
    precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 60.0]
    
    # Aplicar conversión de mes a día si la web lo publica mensualmente (ej. Endesa)
    if conversion_potencia_mes:
        precios_p_raw = [(p * 12) / 365 for p in precios_p_raw]
        
    precios_p = sorted(list(set([p for p in precios_p_raw if 0.01 <= p <= 0.30])))
    
    # Eliminar duplicados secuenciales en energía
    precios_e_unicos = []
    for p in precios_e:
        if not precios_e_unicos or precios_e_unicos[-1] != p:
            precios_e_unicos.append(p)
            
    if len(precios_p) < 2:
        return error_3p if tipo_tarifa == "3P" else error_fijo

    p_valle = precios_p[0]  # El más barato siempre es Valle
    p_punta = precios_p[-1] # El más caro siempre es Punta

    if tipo_tarifa == "FIJO":
        if precios_e_unicos:
            return {"Precio_P_Punta": p_punta, "Precio_P_Valle": p_valle, "Precio_E_Fijo": precios_e_unicos[0]}
        return error_fijo
        
    elif tipo_tarifa == "3P":
        if len(precios_e_unicos) >= 3:
            e_ordenados = sorted(precios_e_unicos[:3])
            return {
                "Precio_P_Punta": p_punta, "Precio_P_Valle": p_valle,
                "Precio_E_Punta": e_ordenados[-1], "Precio_E_Llano": e_ordenados[1], "Precio_E_Valle": e_ordenados[0]
            }
        return error_3p

# --- FUNCIONES ESPECÍFICAS POR COMERCIALIZADORA ---

def procesar_url(url, tipo_tarifa, conversion_potencia_mes=False, click_selector=None):
    html = obtener_html_con_navegador(url, click_selector)
    if not html:
        return {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0} if tipo_tarifa == "FIJO" else {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0}
    
    texto_limpio = limpiar_html_agresivo(html)
    return extraer_precios_texto(texto_limpio, tipo_tarifa, conversion_potencia_mes)

# Iberdrola
def obtener_precios_iberdrola_fijo(): return procesar_url("https://www.iberdrola.es/luz/tarifas/plan-online", "FIJO")
def obtener_precios_iberdrola_3p(): return procesar_url("https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos", "3P")

# EnergyaVM
def obtener_precios_energyavm_fijo(): return procesar_url("https://www.energyavm.es/luz/formula-fija-24-horas-luz/", "FIJO")
def obtener_precios_energyavm_3p(): return procesar_url("https://www.energyavm.es/luz/formula-fija-3-periodos-luz/", "3P")

# Visalia
def obtener_precios_visalia_fijo(): return procesar_url("https://visalia.es/luz/fijo24horas/", "FIJO")
def obtener_precios_visalia_3p(): return procesar_url("https://visalia.es/luz/luz-3-periodos/", "3P")

# Octopus Energy (misma URL, distintos bloques, el extractor ordenará matemáticamente)
def obtener_precios_octopus_fijo(): return procesar_url("https://octopusenergy.es/precios", "FIJO")
def obtener_precios_octopus_3p(): return procesar_url("https://octopusenergy.es/precios", "3P")

# Nufri (Usa selector de clic si está oculto en menú lateral)
def obtener_precios_nufri_fijo(): return procesar_url("https://www.energianufri.com/es/tarifas-luz", "FIJO", click_selector="text='Ver precios'")
def obtener_precios_nufri_3p(): return procesar_url("https://www.energianufri.com/es/tarifas-luz", "3P", click_selector="text='Ver precios'")

# Imagina energía
def obtener_precios_imagina_fijo(): return procesar_url("https://imaginaenergia.com/tarifa-luz-sin-horas/", "FIJO")
def obtener_precios_imagina_3p(): return procesar_url("https://imaginaenergia.com/tarifa-luz-noche-y-findes/", "3P")

# CHC Energía
def obtener_precios_chc_fijo(): return procesar_url("https://chcenergia.es/luz/plan-estrella-duo", "FIJO")

# Naturgy
def obtener_precios_naturgy_fijo(): return procesar_url("https://www.naturgy.es/hogar/luz/tarifa_por_uso_luz", "FIJO")
def obtener_precios_naturgy_3p(): return procesar_url("https://www.naturgy.es/hogar/luz/tarifa_noche", "3P")

# Endesa (Potencia en meses -> conversion_potencia_mes = True)
def obtener_precios_endesa_fijo(): return procesar_url("https://www.endesa.com/es/luz-y-gas/luz/conecta-de-endesa", "FIJO", conversion_potencia_mes=True)
def obtener_precios_endesa_3p():
    # El usuario indica que la tarifa 3P toma la potencia de la web Conecta Luz (Fija)
    datos_3p = procesar_url("https://www.endesa.com/es/luz-y-gas/luz/one/tarifa-one-luz-3periodos", "3P", conversion_potencia_mes=True)
    datos_potencia_fija = procesar_url("https://www.endesa.com/es/luz-y-gas/luz/conecta-de-endesa", "FIJO", conversion_potencia_mes=True)
    
    if datos_potencia_fija["Precio_P_Punta"] > 0:
        datos_3p["Precio_P_Punta"] = datos_potencia_fija["Precio_P_Punta"]
        datos_3p["Precio_P_Valle"] = datos_potencia_fija["Precio_P_Valle"]
    return datos_3p

# Totalenergies
def obtener_precios_totalenergies_fijo(): return procesar_url("https://www.totalenergies.es/es/hogares/tarifas-luz/a-tu-aire-siempre", "FIJO")
def obtener_precios_totalenergies_3p(): return procesar_url("https://www.totalenergies.es/es/hogares/tarifas-luz/a-tu-aire-programa-tu-ahorro", "3P")


def actualizar_fichero_tarifas():
    ruta_json = "tarifas.json"
    if not os.path.exists(ruta_json):
        print(f"⚠️ Error crítico: No se encuentra el fichero {ruta_json}")
        return

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    print("🔄 Iniciando proceso de actualización masiva...")

    # Mapeo de ejecuciones dinámicas
    rutinas = {
        "Iberdrola": {"fijo": obtener_precios_iberdrola_fijo, "3p": obtener_precios_iberdrola_3p},
        "EnergyaVM": {"fijo": obtener_precios_energyavm_fijo, "3p": obtener_precios_energyavm_3p},
        "Visalia": {"fijo": obtener_precios_visalia_fijo, "3p": obtener_precios_visalia_3p},
        "Octopus Energy": {"fijo": obtener_precios_octopus_fijo, "3p": obtener_precios_octopus_3p},
        "Nufri": {"fijo": obtener_precios_nufri_fijo, "3p": obtener_precios_nufri_3p},
        "Imagina energía": {"fijo": obtener_precios_imagina_fijo, "3p": obtener_precios_imagina_3p},
        "CHC Energía": {"fijo": obtener_precios_chc_fijo},
        "Naturgy": {"fijo": obtener_precios_naturgy_fijo, "3p": obtener_precios_naturgy_3p},
        "Endesa": {"fijo": obtener_precios_endesa_fijo, "3p": obtener_precios_endesa_3p},
        "Totalenergies": {"fijo": obtener_precios_totalenergies_fijo, "3p": obtener_precios_totalenergies_3p}
    }

    for tarifa in datos.get("tarifas", []):
        nombre = tarifa.get("Comercializadora", "")
        tipo = tarifa.get("Tipo", "")
        
        if "(Actual)" in nombre or "Tu tarifa" in tipo:
            continue

        print(f"-> Actualizando: {nombre} ({tipo})...")
        nuevos_valores = None
        
        if nombre in rutinas:
            es_3p = "3 periodos" in tipo.lower() or "noche" in tipo.lower() or "horarios" in tipo.lower() or "ahorro" in tipo.lower()
            llave_rutina = "3p" if es_3p else "fijo"
            
            if llave_rutina in rutinas[nombre]:
                nuevos_valores = rutinas[nombre][llave_rutina]()

        if nuevos_valores:
            for clave, valor in nuevos_valores.items():
                tarifa[clave] = valor
            print(f"   ✔ Procesada.")
        else:
            print(f"   ⚠️ Fallo o rutina no definida.")

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print("🎉 ¡Proceso finalizado! Fichero actualizado.")

if __name__ == "__main__":
    actualizar_fichero_tarifas()
