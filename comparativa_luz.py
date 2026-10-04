import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="Comparador de Tarifas de Luz", page_icon="⚡", layout="wide")
st.title("⚡ Comparador Inteligente de Tarifas de Luz (España)")
st.markdown("Calcula y compara en tiempo real las tarifas actualizadas desde tu Google Sheets.")

if "calculado" not in st.session_state:
    st.session_state.calculado = False

SHEET_ID = "1H54QZ3ln7QmHwC5Tf3jF-V4XupIfwZfvSJBJNg3rkTQ"

def limpiar_float(valor):
    """Convierte celdas con comas o puntos decimales a float de forma segura."""
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    val_str = str(valor).strip()
    val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except:
        return 0.0

@st.cache_data(ttl=600)
def cargar_tarifas_desde_sheets():
    """Descarga las dos pestañas de Google Sheets y limpia los formatos numéricos"""
    try:
        # Pestaña de Tarifas Fijas
        url_fija = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Tarifa%20Fija"
        res_fija = requests.get(url_fija)
        df_fijas = pd.read_csv(io.StringIO(res_fija.text))
        
        # Pestaña de Tarifas por Periodos
        url_periodos = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Tarifa%20Periodos"
        res_periodos = requests.get(url_periodos)
        df_periodos = pd.read_csv(io.StringIO(res_periodos.text))
        
        tarifas_db = []
        
        # Procesar Fijas
        for _, row in df_fijas.iterrows():
            if pd.isna(row.get("Comercializadora")): 
                continue
            tarifas_db.append({
                "Comercializadora": str(row.get("Comercializadora", "")).strip(),
                "Tipo": str(row.get("Nombre de la tarifa", "")).strip(),
                "Precio_P_Punta": limpiar_float(row.get("Precio potencia punta", 0)),
                "Precio_P_Valle": limpiar_float(row.get("Precio potencia valle", 0)),
                "Precio_E_Fijo": limpiar_float(row.get("Precio energía", 0))
            })
            
        # Procesar Periodos
        for _, row in df_periodos.iterrows():
            if pd.isna(row.get("Comercializadora")): 
                continue
            tarifas_db.append({
                "Comercializadora": str(row.get("Comercializadora", "")).strip(),
                "Tipo": str(row.get("Nombre de la tarifa", "")).strip(),
                "Precio_P_Punta": limpiar_float(row.get("Precio potencia punta", 0)),
                "Precio_P_Valle": limpiar_float(row.get("Precio potencia valle", 0)),
                "Precio_E_Punta": limpiar_float(row.get("Precio energía punta", 0)),
                "Precio_E_Llano": limpiar_float(row.get("Precio energía llano", 0)),
                "Precio_E_Valle": limpiar_float(row.get("Precio energía valle", 0))
            })
            
        return tarifas_db
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return []

tarifas_db = cargar_tarifas_desde_sheets()
if not tarifas_db: 
    st.warning("⚠️ No se han podido cargar las tarifas desde Google Sheets. Comprueba que las pestañas se llamen 'Tarifa Fija' y 'Tarifa Periodos'.")
    st.stop()

# Detección automática dinámica del número máximo de decimales presentes en los datos
max_decimales = 2
for t in tarifas_db:
    for k in ["Precio_P_Punta", "Precio_P_Valle", "Precio_E_Punta", "Precio_E_Llano", "Precio_E_Valle", "Precio_E_Fijo"]:
        if k in t and isinstance(t[k], (int, float)) and t[k] != 0:
            partes = f"{t[k]:.10f}".rstrip('0').split(".")
            if len(partes) > 1:
                max_decimales = max(max_decimales, len(partes[1]))

def formatear_precio(val):
    if val is None or val == 0: return "⚠️ Error (0 €)" if val == 0 else "-"
    try: return f"{float(val):.{max_decimales}f}"
    except: return str(val)

tarifas_fijas_db = [t for t in tarifas_db if "Precio_E_Fijo" in t]
tarifas_horarias_db = [t for t in tarifas_db if "Precio_E_Fijo" not in t]

with st.expander("📊 Datos de consumo y modalidad de tarifa", expanded=not st.session_state.calculado):
    col_titulo, col_selector = st.columns([2, 1])
    with col_selector:
        modalidad_consumo = st.selectbox("Modalidad de tarifa", ["Tarifa Fija", "Tarifa por Periodos"])

    if modalidad_consumo == "Tarifa Fija":
        col1, col2, col3 = st.columns(3)
        with col1: dias = st.number_input("Días del periodo de facturación", min_value=1, max_value=365, value=30, step=1)
        with col2: potencia = st.number_input("Potencia contratada (kW)", min_value=1.0, max_value=15.0, value=4.6, step=0.1)
        with col3: total_kwh = st.number_input("Energía consumida (kWh)", min_value=0.0, value=300.0, step=1.0)
        
        kwh_punta = total_kwh * 0.25
        kwh_llano = total_kwh * 0.30
        kwh_valle = total_kwh * 0.45
    else:
        col1, col2 = st.columns(2)
        with col1: dias = st.number_input("Días del periodo de facturación", min_value=1, max_value=365, value=30, step=1)
        with col2: potencia = st.number_input("Potencia contratada (kW)", min_value=1.0, max_value=15.0, value=4.6, step=0.1)
        
        st.markdown("**Consumo en kWh por Periodo**")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1: kwh_punta = st.number_input("kWh en Zona Punta", min_value=0.0, value=75.0, step=1.0)
        with col_p2: kwh_llano = st.number_input("kWh en Zona Llano", min_value=0.0, value=90.0, step=1.0)
        with col_p3: kwh_valle = st.number_input("kWh en Zona Valle", min_value=0.0, value=135.0, step=1.0)
        
        total_kwh = kwh_punta + kwh_llano + kwh_valle

    st.info(f"Consumo total acumulado: **{total_kwh:.1f} kWh**")

calcular_pulsado = st.button("🚀 Calcular y Comparar Tarifas", type="primary")

if calcular_pulsado:
    st.session_state.calculado = True
    st.rerun()

if st.session_state.calculado:
    st.markdown("---")
    st.subheader(f"📋 Tarifas Evaluadas ({modalidad_consumo})")
    
    if modalidad_consumo == "Tarifa Fija" and tarifas_fijas_db:
        tabla_fijas_raw = []
        for t in tarifas_fijas_db:
            tipo_orig = t.get("Tipo", "")
            tipo_mod = re.sub(r'\(.*?\)', '(Precio fijo 24h)', tipo_orig) if "(" in tipo_orig else f"{tipo_orig} (Precio fijo 24h)"
            tabla_fijas_raw.append({
                "Comercializadora": t.get("Comercializadora"),
                "Tipo": tipo_mod,
                "Potencia Punta (€/kW·día)": formatear_precio(t.get("Precio_P_Punta")),
                "Potencia Valle (€/kW·día)": formatear_precio(t.get("Precio_P_Valle")),
                "Energía Fija (€/kWh)": formatear_precio(t.get("Precio_E_Fijo")),
            })
        st.dataframe(pd.DataFrame(tabla_fijas_raw), use_container_width=True, hide_index=True)
    elif modalidad_consumo == "Tarifa por Periodos" and tarifas_horarias_db:
        tabla_horarias_raw = []
        for t in tarifas_horarias_db:
            tabla_horarias_raw.append({
                "Comercializadora": t.get("Comercializadora"),
                "Tipo": t.get("Tipo"),
                "Potencia Punta (€/kW·día)": formatear_precio(t.get("Precio_P_Punta")),
                "Potencia Valle (€/kW·día)": formatear_precio(t.get("Precio_P_Valle")),
                "Energía Punta (€/kWh)": formatear_precio(t.get("Precio_E_Punta")),
                "Energía Llano (€/kWh)": formatear_precio(t.get("Precio_E_Llano")),
                "Energía Valle (€/kWh)": formatear_precio(t.get("Precio_E_Valle")),
            })
        st.dataframe(pd.DataFrame(tabla_horarias_raw), use_container_width=True, hide_index=True)
    else:
        st.info("No hay tarifas configuradas para esta modalidad.")

    tarifas_a_comparar = tarifas_fijas_db if modalidad_consumo == "Tarifa Fija" else tarifas_horarias_db
    resultados = []
    alquiler_contador = 0.81 * (dias / 30)

    for t in tarifas_a_comparar:
        p_punta = t.get("Precio_P_Punta", 0.0)
        p_valle = t.get("Precio_P_Valle", 0.0)
        es_fija = "Precio_E_Fijo" in t
        
        if es_fija:
            e_fijo = t.get("Precio_E_Fijo", 0.0)
            tiene_error = (p_punta == 0 or p_valle == 0 or e_fijo == 0)
        else:
            e_punta = t.get("Precio_E_Punta", 0.0)
            e_llano = t.get("Precio_E_Llano", 0.0)
            e_valle = t.get("Precio_E_Valle", 0.0)
            tiene_error = (p_punta == 0 or p_valle == 0 or e_punta == 0 or e_llano == 0 or e_valle == 0)
            
        if tiene_error:
            st.warning(f"⚠️ **Error de datos**: La tarifa **{t.get('Comercializadora')} ({t.get('Tipo')})** tiene precios a 0.")
            continue
        
        coste_potencia = potencia * (p_punta + p_valle) * dias
        
        if es_fija:
            coste_energia = total_kwh * e_fijo
            tipo_etiqueta = "Precio Fijo (24h)"
        else:
            coste_energia = (kwh_punta * e_punta) + (kwh_llano * e_llano) + (kwh_valle * e_valle)
            tipo_etiqueta = t.get("Tipo")
        
        subtotal = coste_potencia + coste_energia + alquiler_contador
        impuesto_electrico = subtotal * 0.025
        base_imponible = subtotal + impuesto_electrico
        total_factura = base_imponible * 1.21
        
        resultados.append({
            "Comercializadora": t.get("Comercializadora"),
            "Tipo": tipo_etiqueta,
            "Coste Potencia (€)": round(coste_potencia, 2),
            "Coste Energía (€)": round(coste_energia, 2),
            "Total Estimado (€)": round(total_factura, 2)
        })

    df_resultados = pd.DataFrame(resultados)
    if not df_resultados.empty:
        df_resultados = df_resultados.sort_values(by="Total Estimado (€)", ascending=True).reset_index(drop=True)

        st.markdown("---")
        st.header(f"🏆 Top Mejores Opciones ({modalidad_consumo})")
        col1, col2, col3 = st.columns(3)
        top_3 = df_resultados.head(3)

        if len(top_3) >= 1: col1.metric(f"🥇 1º - {top_3.loc[0, 'Comercializadora']}", f"{top_3.loc[0, 'Total Estimado (€)']} €", top_3.loc[0, 'Tipo'], "off")
        if len(top_3) >= 2: col2.metric(f"🥈 2º - {top_3.loc[1, 'Comercializadora']}", f"{top_3.loc[1, 'Total Estimado (€)']} €", top_3.loc[1, 'Tipo'], "off")
        if len(top_3) >= 3: col3.metric(f"🥉 3º - {top_3.loc[2, 'Comercializadora']}", f"{top_3.loc[2, 'Total Estimado (€)']} €", top_3.loc[2, 'Tipo'], "off")

        st.markdown("---")
        st.subheader("📊 Comparativa Global de Costes Estimados")
        st.dataframe(df_resultados, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No hay comercializadoras disponibles para calcular (todas las tarifas presentan errores o precios a 0).")
