import re
import requests
from bs4 import BeautifulSoup

def obtener_html(url):
    """Realiza una petición HTTP estándar para descargar el HTML de EnergyaVM."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
        else:
            print(f"⚠️ Error HTTP {response.status_code} al acceder a {url}")
            return None
    except Exception as e:
        print(f"⚠️ Excepción de red en EnergyaVM ({url}): {e}")
        return None

def extraer_precios_de_html(html, es_3p=False):
    """Limpia el HTML y extrae los precios de energía y potencia mediante expresiones regulares."""
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style", "noscript"]):
        script.extract()
        
    texto = soup.get_text(separator=' ')
    texto_limpio = texto.replace('&euro;', '€').replace('&#8364;', '€').replace('&nbsp;', ' ')
    t_lower = ' '.join(texto_limpio.split()).lower()
    
    # Extraer todos los valores seguidos de €/kWh y €/kW
    matches_energia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kwh', t_lower)
    matches_potencia = re.findall(r'(\d+[,\.]\d+)\s*€\s*/\s*kw', t_lower)
    
    precios_e_raw = [float(p.replace(',', '.')) for p in matches_energia if 0.03 <= float(p.replace(',', '.')) <= 0.50]
    precios_p_raw = [float(p.replace(',', '.')) for p in matches_potencia if 0.005 <= float(p.replace(',', '.')) <= 0.50]
    
    # Filtrar duplicados consecutivos en energía
    precios_e_unicos = []
    for p in precios_e_raw:
        if not precios_e_unicos or precios_e_unicos[-1] != p:
            precios_e_unicos.append(p)
            
    precios_p = sorted(list(set(precios_p_raw)))
    
    if not es_3p:
        # Tarifa Fija 24h
        error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
        if precios_e_unicos and len(precios_p) >= 2:
            return {
                "Precio_P_Punta": max(precios_p),
                "Precio_P_Valle": min(precios_p),
                "Precio_E_Fijo": precios_e_unicos[0]
            }
    else:
        # Tarifa 3 Periodos
        error_return = {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0}
        if len(precios_e_unicos) >= 3 and len(precios_p) >= 2:
            e_ordenados = sorted(precios_e_unicos[:3])
            return {
                "Precio_P_Punta": max(precios_p),
                "Precio_P_Valle": min(precios_p),
                "Precio_E_Punta": e_ordenados[-1],
                "Precio_E_Llano": e_ordenados[1],
                "Precio_E_Valle": e_ordenados[0]
            }
            
    return error_return

def obtener_precios_fijo():
    """Extrae los precios de la Tarifa Fija 24h de EnergyaVM"""
    url = "https://www.energyavm.es/luz/formula-fija-24-horas-luz/"
    html = obtener_html(url)
    if not html:
        return {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Fijo": 0}
    return extraer_precios_de_html(html, es_3p=False)

def obtener_precios_3p():
    """Extrae los precios de la Tarifa 3 Periodos de EnergyaVM"""
    url = "https://www.energyavm.es/luz/formula-fija-3-periodos-luz/"
    html = obtener_html(url)
    if not html:
        return {"Precio_P_Punta": 0, "Precio_P_Valle": 0, "Precio_E_Punta": 0, "Precio_E_Llano": 0, "Precio_E_Valle": 0}
    return extraer_precios_de_html(html, es_3p=True)
