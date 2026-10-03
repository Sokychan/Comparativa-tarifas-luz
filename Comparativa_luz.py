import streamlit as st
import pandas as pd
import json
import os
import re

# Configuración de la página
st.set_page_config(
    page_title="Comparador de Tarifas de Luz",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Comparador Inteligente de Tarifas de Luz (España)")
st.markdown("""
Calcula y compara de forma automática qué comercializadora se adapta mejor al consumo real. 
Introduce los datos a continuación y pulsa el botón para calcular.
""")

# --- INICIALIZACIÓN DE ESTADO ---
if "calculado" not in st.session_state:
    st.session_state.calculado = False

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

# --- CÁLCULO DINÁMICO DE DECIMALES MÁXIMOS ---
max_decimales = 2
for t in tarifas_db:
    for k in ["Precio_P_Punta", "Precio_P_Valle", "Precio_E_Punta", "Precio_E_Llano", "Precio_E_Valle", "Precio_E_Fijo"]:
        if k in t and isinstance(t[k], (int, float)):
            partes = str(t[k]).split(".")
            if len(partes) > 1:
                max_decimales = max(max_decimales, len(partes[1]))

def formatear_precio(val):
    if val is None:
        return "-"
    try:
        return f"{float(val):.{max_decimales}f}"
    except (ValueError, TypeError):
        return str(val)

# Separar listas de tarifas fijas y horarias para uso interno
tarifas_fijas_db = [t for t in tarifas_db if "Precio_E_Fijo" in t]
tarifas_horarias_db = [t for t in tarifas_db if "Precio_E_Fijo" not in t]

# --- CONFIGURACIÓN DE DATOS DE CONSUMO EN EXPANDER DINÁMICO ---
# El expander se muestra abierto por defecto y se oculta/contrae automáticamente tras pulsar calcular
with st.expander("📊 Datos de consumo y modalidad de tarifa", expanded=not st.session_state.calculado):
    col_titulo, col_selector = st.columns([2, 1])
    with col_selector:
        modalidad_consumo = st.selectbox(
            "Modalidad de tarifa",
            ["Tarifa Fija", "Tarifa por Periodos"]
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

# Botón de confirmación para realizar la comparación
calcular_pulsado = st.button("🚀 Calcular y Comparar Tarifas", type="primary")

if calcular_pulsado:
    st.session_state.calculado = True
    st.rerun()

# --- MOTOR DE CÁLCULO Y RESULTADOS ---
if st.session_state.calculado:
    st.markdown("---")
    
    # 1. Mostrar la tabla del tipo de tarifa seleccionado
    st.subheader(f"📋 Tarifas Evaluadas ({modalidad_consumo})")
    if modalidad_consumo == "Tarifa Fija" and tarifas_fijas_db:
        tabla_fijas_raw = []
        for t in tarifas_fijas_db:
            tipo_orig = t.get("Tipo", "")
            if "(" in tipo_orig and ")" in tipo_orig:
                tipo_mod = re.sub(r'\(.*?\)', '(Precio fijo 24h)', tipo_orig)
            else:
                tipo_mod = f"{tipo_orig} (Precio fijo 24h)"
                
            tabla_fijas_raw.append({
                "Comercializadora": t.get("Comercializadora"),
                "Tipo": tipo_mod,
                "Potencia Punta (€/kW·día)": formatear_precio(t.get("Precio_P_Punta")),
                "Potencia Valle (€/kW·día)": formatear_precio(t.get("Precio_P_Valle")),
                "Energía Fija (€/kWh)": formatear_precio(t.get("Precio_E_Fijo")),
            })
        df_fijas = pd.DataFrame(tabla_fijas_raw)
        st.dataframe(df_fijas, use_container_width=True, hide_index=True)
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
        df_horarias = pd.DataFrame(tabla_horarias_raw)
        st.dataframe(df_horarias, use_container_width=True, hide_index=True)
    else:
        st.info("No hay tarifas configuradas para esta modalidad.")

    # Filtrar tarifas según la modalidad de consumo elegida por el cliente para el cálculo
    if modalidad_consumo == "Tarifa Fija":
        tarifas_a_comparar = tarifas_fijas_db
    else:
        tarifas_a_comparar = tarifas_horarias_db

    resultados = []
    alquiler_contador = 0.81 * (dias / 30)  # Coste estimado alquiler de contador mensual

    for t in tarifas_a_comparar:
        p_punta = t.get("Precio_P_Punta", 0.0)
        p_valle = t.get("Precio_P_Valle", 0.0)
        
        # Coste de potencia (repartido simétricamente entre P1 y P2 para la simulación)
        coste_potencia = potencia * (p_punta + p_valle) * (dias / 2)
        
        # Coste de energía según si es precio fijo o discriminación horaria
        if "Precio_E_Fijo" in t:
            coste_energia = total_kwh * t["Precio_E_Fijo"]
            tipo_etiqueta = "Precio Fijo (24h)"
        else:
            coste_energia = (
                (kwh_punta * t.get("Precio_E_Punta", 0.0)) + 
                (kwh_llano * t.get("Precio_E_Llano", 0.0)) + 
                (kwh_valle * t.get("Precio_E_Valle", 0.0))
            )
            tipo_etiqueta = t.get("Tipo")
        
        # Subtotal antes de impuestos
        subtotal = coste_potencia + coste_energia + alquiler_contador
        
        # Impuestos en España (Impuesto eléctrico reducido ~2.5% + IVA general 21%)
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

    # Convertir a DataFrame de Pandas, ordenar de menor a mayor precio y eliminar índice visual
    df_resultados = pd.DataFrame(resultados)
    if not df_resultados.empty:
        df_resultados = df_resultados.sort_values(by="Total Estimado (€)", ascending=True).reset_index(drop=True)

        # 2. Mostrar el ranking de las 3 mejores opciones
        st.markdown("---")
        st.header(f"🏆 Top Mejores Opciones ({modalidad_consumo})")

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

        # 3. Mostrar el resumen de precios de todas las comercializadoras comparadas
        st.markdown("---")
        st.subheader("📊 Comparativa Global de Costes Estimados")
        st.dataframe(df_resultados, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay comercializadoras disponibles para la modalidad seleccionada.")
