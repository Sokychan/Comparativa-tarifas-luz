import streamlit as st
import pandas as pd
import json
import os

# Configuración de la página
st.set_page_config(
    page_title="Comparador de Tarifas de Luz",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Comparador Inteligente de Tarifas de Luz (España)")
st.markdown("""
Calcula y compara de forma automática qué comercializadora se adapta mejor a tu consumo real. 
Introduce tus datos en el panel desplegable inferior para actualizar los resultados.
""")

# --- PANEL DESPLEGABLE DE ENTRADA DE DATOS DE CONSUMO ---
with st.expander("📝 Configuración de Datos de Consumo", expanded=True):
    col_titulo, col_selector = st.columns([2, 1])
    with col_titulo:
        st.subheader("📊 Datos de consumo")
    with col_selector:
        modalidad_consumo = st.selectbox(
            "Modalidad de tarifa",
            ["Tarifa Fija", "Tarifa por Periodos"],
            label_visibility="collapsed"
        )
    
    if modalidad_consumo == "Tarifa Fija":
        col1, col2, col3 = st.columns(3)
        with col1:
            dias = st.number_input("Días del periodo de facturación", min_value=1, max_value=365, value=30, step=1)
        with col2:
            potencia = st.number_input("Potencia contratada (kW)", min_value=1.0, max_value=15.0, value=4.6, step=0.1)
        with col3:
            total_kwh = st.number_input("Energía consumida (kWh)", min_value=0.0, value=300.0, step=1.0)
        
        # Distribución estimada estándar para la simulación en tarifas con periodos
        kwh_punta = total_kwh * 0.25
        kwh_llano = total_kwh * 0.30
        kwh_valle = total_kwh * 0.45
    else:
        col1, col2 = st.columns(2)
        with col1:
            dias = st.number_input("Días del periodo de facturación", min_value=1, max_value=365, value=30, step=1)
        with col2:
            potencia = st.number_input("Potencia contratada (kW)", min_value=1.0, max_value=15.0, value=4.6, step=0.1)
        
        st.markdown("**Consumo en kWh por Periodo**")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            kwh_punta = st.number_input("kWh en Zona Punta", min_value=0.0, value=75.0, step=1.0)
        with col_p2:
            kwh_llano = st.number_input("kWh en Zona Llano", min_value=0.0, value=90.0, step=1.0)
        with col_p3:
            kwh_valle = st.number_input("kWh en Zona Valle", min_value=0.0, value=135.0, step=1.0)
        
        total_kwh = kwh_punta + kwh_llano + kwh_valle
    
    st.info(f"Consumo total acumulado: **{total_kwh:.1f} kWh**")

# --- CARGA DINÁMICA DE TARIFAS DESDE EL FICHERO .JSON ---
ARCHIVO_JSON = "tarifas.json"

def cargar_tarifas_json(ruta):
    """Carga la base de datos de tarifas desde un archivo JSON local de forma segura."""
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = json.load(f)
                return contenido.get("tarifas", [])
        except Exception as e:
            st.error(f"Error al leer el archivo JSON de tarifas: {e}")
            return []
    else:
        st.warning(f"⚠️ No se ha encontrado el archivo `{ruta}`. Se utilizará una estructura de ejemplo integrada.")
        return [
            {
                "Comercializadora": "PVPC (Regulado REE)",
                "Tipo": "Discriminación Horaria (3 periodos)",
                "Precio_P_Punta": 0.0820,
                "Precio_P_Valle": 0.0210,
                "Precio_E_Punta": 0.1650,
                "Precio_E_Llano": 0.1320,
                "Precio_E_Valle": 0.0910,
            },
            {
                "Comercializadora": "Octopus Energy",
                "Tipo": "Precio Fijo (24h)",
                "Precio_P_Punta": 0.0900,
                "Precio_P_Valle": 0.0250,
                "Precio_E_Fijo": 0.1300,
            },
            {
                "Comercializadora": "Iberdrola",
                "Tipo": "Plan Online (Precio Fijo)",
                "Precio_P_Punta": 0.1100,
                "Precio_P_Valle": 0.0300,
                "Precio_E_Fijo": 0.1420,
            },
            {
                "Comercializadora": "Endesa",
                "Tipo": "One Luz (Precio Fijo)",
                "Precio_P_Punta": 0.1050,
                "Precio_P_Valle": 0.0280,
                "Precio_E_Fijo": 0.1380,
            }
        ]

tarifas_db = cargar_tarifas_json(ARCHIVO_JSON)

if not tarifas_db:
    st.stop()

# --- TABLA DE PRECIOS DE LAS COMERCIALIZADORAS (3 DECIMALES) ---
st.subheader("📋 Precios Unitarios de las Tarifas del Mercado")
tabla_precios_raw = []
for t in tarifas_db:
    tabla_precios_raw.append({
        "Comercializadora": t.get("Comercializadora"),
        "Tipo": t.get("Tipo"),
        "Potencia Punta (€/kW·día)": f"{t.get('Precio_P_Punta', 0.0):.3f}",
        "Potencia Valle (€/kW·día)": f"{t.get('Precio_P_Valle', 0.0):.3f}",
        "Energía Punta (€/kWh)": f"{t.get('Precio_E_Punta', t.get('Precio_E_Fijo', 0.0)):.3f}",
        "Energía Llano (€/kWh)": f"{t.get('Precio_E_Llano', t.get('Precio_E_Fijo', 0.0)):.3f}",
        "Energía Valle (€/kWh)": f"{t.get('Precio_E_Valle', t.get('Precio_E_Fijo', 0.0)):.3f}",
    })
df_precios_json = pd.DataFrame(tabla_precios_raw)
st.dataframe(df_precios_json, use_container_width=True)

st.markdown("---")

# --- MOTOR DE CÁLCULO ---
resultados = []
alquiler_contador = 0.81 * (dias / 30)  # Coste estimado alquiler de contador mensual

for t in tarifas_db:
    p_punta = t.get("Precio_P_Punta", 0.0)
    p_valle = t.get("Precio_P_Valle", 0.0)
    
    # Coste de potencia (repartido simétricamente entre P1 y P2 para la simulación)
    coste_potencia = potencia * (p_punta + p_valle) * (dias / 2)
    
    # Coste de energía según si es precio fijo o discriminación horaria
    if "Precio_E_Fijo" in t:
        coste_energia = total_kwh * t["Precio_E_Fijo"]
    else:
        coste_energia = (
            (kwh_punta * t.get("Precio_E_Punta", 0.0)) + 
            (kwh_llano * t.get("Precio_E_Llano", 0.0)) + 
            (kwh_valle * t.get("Precio_E_Valle", 0.0))
        )
    
    # Subtotal antes de impuestos
    subtotal = coste_potencia + coste_energia + alquiler_contador
    
    # Impuestos en España (Impuesto eléctrico reducido ~2.5% + IVA general 21%)
    impuesto_electrico = subtotal * 0.025
    base_imponible = subtotal + impuesto_electrico
    total_factura = base_imponible * 1.21
    
    resultados.append({
        "Comercializadora": t.get("Comercializadora"),
        "Tipo": t.get("Tipo"),
        "Coste Potencia (€)": round(coste_potencia, 2),
        "Coste Energía (€)": round(coste_energia, 2),
        "Total Estimado (€)": round(total_factura, 2)
    })

# Convertir a DataFrame de Pandas y ordenar de menor a mayor precio
df_resultados = pd.DataFrame(resultados)
df_resultados = df_resultados.sort_values(by="Total Estimado (€)", ascending=True).reset_index(drop=True)

# --- VISUALIZACIÓN DE RESULTADOS ---
st.header("🏆 Top 3 Mejores Opciones Según tu Consumo")

col1, col2, col3 = st.columns(3)
top_3 = df_resultados.head(3)

if len(top_3) >= 1:
    with col1:
        st.metric(
            label=f"🥇 1º - {top_3.loc[0, 'Comercializadora']}",
            value=f"{top_3.loc[0, 'Total Estimado (€)']} €",
            delta=top_3.loc[0, 'Tipo'],
            delta_color="off"
        )
if len(top_3) >= 2:
    with col2:
        st.metric(
            label=f"🥈 2º - {top_3.loc[1, 'Comercializadora']}",
            value=f"{top_3.loc[1, 'Total Estimado (€)']} €",
            delta=top_3.loc[1, 'Tipo'],
            delta_color="off"
        )
if len(top_3) >= 3:
    with col3:
        st.metric(
            label=f"🥉 3º - {top_3.loc[2, 'Comercializadora']}",
            value=f"{top_3.loc[2, 'Total Estimado (€)']} €",
            delta=top_3.loc[2, 'Tipo'],
            delta_color="off"
        )

st.markdown("---")
st.subheader("📊 Comparativa Global de Costes Estimados")
st.dataframe(df_resultados, use_container_width=True)
