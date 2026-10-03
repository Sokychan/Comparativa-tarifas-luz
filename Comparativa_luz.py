import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Comparador de Tarifas de Luz",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Comparador Inteligente de Tarifas de Luz (España)")
st.markdown("""
Calcula y compara de forma automática qué comercializadora se adapta mejor a tu estilo de vida y consumo real. 
Introduce tus datos en la barra lateral para ver los resultados actualizados.
""")

# --- BARRA LATERAL: ENTRADA DE DATOS ---
st.sidebar.header("📝 Tus Datos de Facturación")

dias = st.sidebar.number_input("Días del periodo de facturación", min_value=1, max_value=365, value=30, step=1)
potencia = st.sidebar.number_input("Potencia contratada (kW)", min_value=1.0, max_value=15.0, value=4.6, step=0.1)

st.sidebar.subheader("Consumo en kWh por Periodo")
kwh_punta = st.sidebar.number_input("kWh en Zona Punta", min_value=0.0, value=75.0, step=1.0)
kwh_llano = st.sidebar.number_input("kWh en Zona Llano", min_value=0.0, value=90.0, step=1.0)
kwh_valle = st.sidebar.number_input("kWh en Zona Valle", min_value=0.0, value=135.0, step=1.0)

total_kwh = kwh_punta + kwh_llano + kwh_valle
st.sidebar.info(f"Consumo total acumulado: **{total_kwh:.1f} kWh**")

# --- BASE DE DATOS DE TARIFAS (MODELO 2.0TD) ---
# Precios de referencia orientativos (€/kW·día para potencia y €/kWh para energía)
# Nota: Puedes actualizar estos valores periódicamente o conectarlos a una API externa (ej. REE/ESIOS).
tarifas_db = [
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
    },
    {
        "Comercializadora": "Naturgy",
        "Tipo": "Tarifa Compromiso (Discriminación)",
        "Precio_P_Punta": 0.0950,
        "Precio_P_Valle": 0.0220,
        "Precio_E_Punta": 0.1700,
        "Precio_E_Llano": 0.1400,
        "Precio_E_Valle": 0.1000,
    },
    {
        "Comercializadora": "TotalEnergies",
        "Tipo": "A Tu Aire FáciL (Precio Fijo)",
        "Precio_P_Punta": 0.0880,
        "Precio_P_Valle": 0.0240,
        "Precio_E_Fijo": 0.1280,
    }
]

# --- MOTOR DE CÁLCULO ---
resultados = []
alquiler_contador = 0.81 * (dias / 30)  # Coste estimado alquiler de contador mensual

for t in tarifas_db:
    # Coste de potencia (asumiendo reparto simétrico aproximado entre P1 y P2 para simplificar la simulación)
    coste_potencia = potencia * (t["Precio_P_Punta"] + t["Precio_P_Valle"]) * (dias / 2)
    
    # Coste de energía según si es precio fijo o discriminación horaria
    if "Precio_E_Fijo" in t:
        coste_energia = total_kwh * t["Precio_E_Fijo"]
    else:
        coste_energia = (
            (kwh_punta * t["Precio_E_Punta"]) + 
            (kwh_llano * t["Precio_E_Llano"]) + 
            (kwh_valle * t["Precio_E_Valle"])
        )
    
    # Subtotal antes de impuestos
    subtotal = coste_potencia + coste_energia + alquiler_contador
    
    # Impuestos en España (Impuesto eléctrico reducido ~2.5% + IVA general 21%)
    impuesto_electrico = subtotal * 0.025
    base_imponible = subtotal + impuesto_electrico
    total_factura = base_imponible * 1.21
    
    resultados.append({
        "Comercializadora": t["Comercializadora"],
        "Tipo": t["Tipo"],
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
            value=f"{top_3.loc[0, 'Total Estimado (€)]']} €",
            delta=top_3.loc[0, 'Tipo'],
            delta_color="off"
        )
if len(top_3) >= 2:
    with col2:
        st.metric(
            label=f"🥈 2º - {top_3.loc[1, 'Comercializadora']}",
            value=f"{top_3.loc[1, 'Total Estimado (€)]']} €",
            delta=top_3.loc[1, 'Tipo'],
            delta_color="off"
        )
if len(top_3) >= 3:
    with col3:
        st.metric(
            label=f"🥉 3º - {top_3.loc[2, 'Comercializadora']}",
            value=f"{top_3.loc[2, 'Total Estimado (€)]']} €",
            delta=top_3.loc[2, 'Tipo'],
            delta_color="off"
        )

st.markdown("---")
st.subheader("📊 Comparativa Global de Todas las Tarifas")
st.dataframe(df_resultados, use_container_width=True)

# Gráfico de barras comparativo
st.bar_chart(df_resultados.set_index("Comercializadora")["Total Estimado (€)"])
