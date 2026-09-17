import os
from dotenv import load_dotenv
from supabase import create_client, Client
import streamlit as st
import pandas as pd
import io
from procesadores_bancos import PROCESADORES

# Cargar variables de entorno
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = None
if url and key:
    supabase = create_client(url, key)

st.set_page_config(page_title="Asientos Contables Bancarios", page_icon="🏦", layout="wide")

# --- USUARIOS PERMITIDOS ---
# Aquí puedes cambiar los nombres y contraseñas (4 dígitos)
USUARIOS = {
    "Laura": "1111",
    "Maria": "2222",
    "Tato": "3333"
}

def login():
    st.markdown("## 🔒 Acceso Restringido")
    st.markdown("Por favor, identifícate para ingresar al sistema contable.")
    
    with st.form("login_form"):
        usuario = st.selectbox("Usuario", list(USUARIOS.keys()))
        password = st.text_input("Contraseña (PIN)", type="password")
        submit = st.form_submit_button("Ingresar")
        
        if submit:
            if USUARIOS.get(usuario) == password:
                st.session_state["usuario_actual"] = usuario
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")

def main():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    # Inyectar CSS personalizado
    st.markdown("""
        <style>
        div[data-testid="stExpander"] details summary p {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            color: #1f2937 !important;
        }
        div[data-testid="stExpander"] details summary {
            background-color: #f3f4f6;
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
        }
        .block-container {
            max-width: 1200px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Mostrar logo si existe (centrado para el login)
    if not st.session_state["logged_in"]:
        if os.path.exists("logo.png"):
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                st.image("logo.png", use_container_width=True)
        login()
        return

    # Si está logueado, mostrar la app normal
    if os.path.exists("logo.png"):
        st.sidebar.image("logo.png", use_container_width=True)
        
    st.sidebar.markdown(f"👤 **Usuario:** {st.session_state['usuario_actual']}")
    st.sidebar.markdown("---")
    
    st.sidebar.title("Navegación")
    modo = st.sidebar.radio("Ir a:", ["Cargar Banco", "Reporte Consolidado"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state["logged_in"] = False
        st.rerun()
    
    if modo == "Cargar Banco":
        vista_carga()
    else:
        vista_reportes()

def vista_carga():
    st.title("🏦 Generador de Asientos Contables")
    st.markdown("Sube tu extracto bancario para agrupar los movimientos por concepto y generar el asiento contable.")

    # Selección de Banco
    bancos_disponibles = list(PROCESADORES.keys())
    banco_seleccionado = st.selectbox("Selecciona el Banco", bancos_disponibles)

    # Subida de archivo
    uploaded_file = st.file_uploader(f"Sube el archivo Excel o CSV del {banco_seleccionado}", type=['xlsx', 'xls', 'csv'])

    if uploaded_file is not None:
        try:
            with st.spinner('Procesando archivo...'):
                funcion_procesar = PROCESADORES[banco_seleccionado]
                df_raw = funcion_procesar(uploaded_file)
                
            # Asegurar formato de fecha (dayfirst=True para que 02/09 sea 2 de septiembre)
            df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'], errors='coerce', dayfirst=True)
            df = df_raw.copy()
            
            st.success("Archivo procesado exitosamente!")
            
            if supabase:
                if st.button("💾 Guardar estos movimientos en la Base de Datos"):
                    with st.spinner("Guardando en la nube..."):
                        # Preparar registros
                        registros = []
                        for _, row in df_raw.iterrows():
                            # Asegurar que no haya NaTs o NaNs problemáticos
                            if pd.isna(row['Fecha']): continue
                            registros.append({
                                "fecha": row['Fecha'].strftime('%Y-%m-%d'),
                                "banco": banco_seleccionado,
                                "concepto_original": str(row['Detalle_Original']),
                                "concepto_agrupador": str(row['Concepto_Agrupador']),
                                "importe": float(row['Importe']),
                                "tipo": "INGRESO" if row['Importe'] > 0 else "EGRESO"
                            })
                        
                        try:
                            # Insertar en lotes si es muy grande, pero normalmente 1000 filas entra bien
                            respuesta = supabase.table("movimientos_bancarios").insert(registros).execute()
                            st.success(f"¡Se guardaron {len(registros)} movimientos exitosamente en la nube!")
                        except Exception as db_err:
                            st.error(f"Error al guardar en base de datos: {str(db_err)}")
                            st.info("Asegúrate de haber creado la tabla en Supabase con el script 'crear_tablas.sql'.")
            
            st.markdown("### 🔍 Filtros")
            col_search, col_date = st.columns(2)
            
            with col_search:
                texto_filtro = st.text_input("Buscar por concepto o movimiento...", "")
                
            with col_date:
                min_date = df['Fecha'].min().date() if not pd.isna(df['Fecha'].min()) else None
                max_date = df['Fecha'].max().date() if not pd.isna(df['Fecha'].max()) else None
                
                if min_date and max_date:
                    # value puede ser una tupla con dos fechas para un rango
                    fechas_rango = st.date_input("Filtrar por Fecha (elige el mismo día 2 veces para un día exacto)", value=(min_date, max_date), min_value=min_date, max_value=max_date)
                else:
                    fechas_rango = None
                    
            # APLICAR FILTROS
            if texto_filtro:
                mask_concepto = df['Concepto_Agrupador'].str.contains(texto_filtro, case=False, na=False)
                mask_detalle = df['Detalle_Original'].str.contains(texto_filtro, case=False, na=False)
                df = df[mask_concepto | mask_detalle]
                
            if fechas_rango:
                if len(fechas_rango) == 2:
                    inicio, fin = fechas_rango
                    mask_fecha = (df['Fecha'].dt.date >= inicio) & (df['Fecha'].dt.date <= fin)
                    df = df[mask_fecha]
                elif len(fechas_rango) == 1:
                    inicio = fechas_rango[0]
                    mask_fecha = df['Fecha'].dt.date == inicio
                    df = df[mask_fecha]
            
            st.markdown("---")
            
            if df.empty:
                st.warning("No hay movimientos que coincidan con los filtros aplicados.")
            else:
                # Separar el detalle en Entradas (Positivos) y Salidas (Negativos) antes de agrupar
                df_entradas = df[df['Importe'] > 0].copy()
                df_salidas = df[df['Importe'] < 0].copy()
                
                # Agrupar por separado
                df_ingresos = df_entradas.groupby('Concepto_Agrupador')['Importe'].sum().reset_index()
                df_ingresos['Importe'] = df_ingresos['Importe'].round(2)
                df_ingresos = df_ingresos.sort_values(by='Importe', ascending=False)
                
                df_egresos = df_salidas.groupby('Concepto_Agrupador')['Importe'].sum().reset_index()
                df_egresos['Importe'] = df_egresos['Importe'].round(2)
                df_egresos = df_egresos.sort_values(by='Importe', ascending=True)
                
                # Cálculos totales
                total_debitos = df_salidas['Importe'].sum()
                total_creditos = df_entradas['Importe'].sum()
                saldo_neto = df['Importe'].sum()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Débitos (Salidas)", f"$ {total_debitos:,.2f}")
                col2.metric("Total Créditos (Entradas)", f"$ {total_creditos:,.2f}")
                col3.metric("Saldo Neto", f"$ {saldo_neto:,.2f}")

                st.markdown("---")
                
                # Preparar formato de Asiento Contable para Exportar
                lista_asiento = []
                for _, row in df_egresos.iterrows():
                    lista_asiento.append({
                        'Concepto_Agrupador': row['Concepto_Agrupador'],
                        'Debe (Egresos)': abs(row['Importe']),
                        'Haber (Ingresos)': 0.0
                    })
                for _, row in df_ingresos.iterrows():
                    lista_asiento.append({
                        'Concepto_Agrupador': row['Concepto_Agrupador'],
                        'Debe (Egresos)': 0.0,
                        'Haber (Ingresos)': row['Importe']
                    })
                df_asiento = pd.DataFrame(lista_asiento)
                
                # Exportar a Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
                    if not df_asiento.empty:
                        df_asiento.to_excel(writer, index=False, sheet_name='Resumen_Asiento')
                    # Asegurar que la fecha se exporte limpia
                    df_export = df.copy()
                    df_export['Fecha'] = df_export['Fecha'].dt.date
                    df_export.to_excel(writer, index=False, sheet_name='Detalle_Movimientos')
                
                st.download_button(
                    label="📥 Descargar Vista Actual en Excel (con Debe y Haber)",
                    data=output.getvalue(),
                    file_name=f"asiento_{banco_seleccionado}_filtrado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.markdown("---")
                st.markdown("### Detalle para Control")
                
                # Usar Pestañas (Tabs) para separar visualmente
                tab_egresos, tab_ingresos = st.tabs(["🔴 EGRESOS (Débitos)", "🟢 INGRESOS (Créditos)"])
                
                with tab_egresos:
                    if df_egresos.empty:
                        st.info("No hay movimientos de egreso para mostrar.")
                    else:
                        for _, row in df_egresos.iterrows():
                            concepto = row['Concepto_Agrupador']
                            total = row['Importe']
                            detalle = df_salidas[df_salidas['Concepto_Agrupador'] == concepto].copy()
                            detalle['Fecha'] = detalle['Fecha'].dt.date
                            if not detalle.empty:
                                with st.expander(f"{concepto} | Total: $ {total:,.2f} ({len(detalle)} movs)"):
                                    st.dataframe(detalle, use_container_width=True, hide_index=True)
                                
                with tab_ingresos:
                    if df_ingresos.empty:
                        st.info("No hay movimientos de ingreso para mostrar.")
                    else:
                        for _, row in df_ingresos.iterrows():
                            concepto = row['Concepto_Agrupador']
                            total = row['Importe']
                            detalle = df_entradas[df_entradas['Concepto_Agrupador'] == concepto].copy()
                            detalle['Fecha'] = detalle['Fecha'].dt.date
                            if not detalle.empty:
                                with st.expander(f"{concepto} | Total: $ {total:,.2f} ({len(detalle)} movs)"):
                                    st.dataframe(detalle, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")
            st.info("Asegúrate de que el archivo tenga el formato correcto para el banco seleccionado.")

def vista_reportes():
    st.title("📊 Reporte Consolidado Histórico")
    
    if not supabase:
        st.error("No hay conexión a Supabase configurada. Revisa el archivo .env.")
        return
        
    with st.spinner("Descargando datos consolidados..."):
        try:
            # Obtener datos de Supabase. Límite alto por si hay muchos.
            response = supabase.table("movimientos_bancarios").select("*").limit(50000).execute()
            data = response.data
            
            if not data:
                st.info("Aún no has guardado ningún movimiento en la nube.")
                return
                
            df = pd.DataFrame(data)
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['Mes'] = df['fecha'].dt.to_period('M').astype(str)
            
            st.markdown("### 🔍 Filtros del Reporte")
            col1, col2 = st.columns(2)
            
            with col1:
                meses_disponibles = sorted(df['Mes'].unique(), reverse=True)
                mes_seleccionado = st.selectbox("Seleccionar Mes", meses_disponibles)
            
            with col2:
                bancos_disponibles = sorted(df['banco'].unique())
                bancos_seleccionados = st.multiselect("Filtrar Bancos", bancos_disponibles, default=bancos_disponibles)
                
            # Aplicar filtros
            df_filtrado = df[df['Mes'] == mes_seleccionado]
            if bancos_seleccionados:
                df_filtrado = df_filtrado[df_filtrado['banco'].isin(bancos_seleccionados)]
                
            if df_filtrado.empty:
                st.warning("No hay datos para la selección actual.")
                return
                
            st.markdown("---")
            
            # Agrupar conceptos sumando importes de todos los bancos mezclados
            df_agrupado = df_filtrado.groupby(['concepto_agrupador', 'tipo'])['importe'].sum().reset_index()
            
            df_ingresos = df_agrupado[df_agrupado['tipo'] == 'INGRESO'].sort_values(by='importe', ascending=False)
            df_egresos = df_agrupado[df_agrupado['tipo'] == 'EGRESO'].sort_values(by='importe', ascending=True)
            
            # Cálculos totales
            total_ingresos = df_ingresos['importe'].sum()
            total_egresos = df_egresos['importe'].sum()
            saldo_neto = total_ingresos + total_egresos
            
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("Total Egresos", f"$ {total_egresos:,.2f}")
            col_t2.metric("Total Ingresos", f"$ {total_ingresos:,.2f}")
            col_t3.metric("Saldo Mensual Neto", f"$ {saldo_neto:,.2f}")
            
            st.markdown("---")
            
            # Exportar a Excel Consolidado
            # Preparar formato Asiento
            lista_asiento = []
            for _, row in df_egresos.iterrows():
                lista_asiento.append({
                    'Concepto_Agrupador': row['concepto_agrupador'],
                    'Debe (Egresos)': abs(row['importe']),
                    'Haber (Ingresos)': 0.0
                })
            for _, row in df_ingresos.iterrows():
                lista_asiento.append({
                    'Concepto_Agrupador': row['concepto_agrupador'],
                    'Debe (Egresos)': 0.0,
                    'Haber (Ingresos)': row['importe']
                })
            df_asiento = pd.DataFrame(lista_asiento)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
                if not df_asiento.empty:
                    df_asiento.to_excel(writer, index=False, sheet_name='Consolidado_Asiento')
                
                # Detalle de todos los movimientos que componen este reporte
                df_export = df_filtrado.copy()
                df_export['fecha'] = df_export['fecha'].dt.date
                df_export.drop(columns=['id', 'created_at', 'Mes'], inplace=True, errors='ignore')
                df_export.to_excel(writer, index=False, sheet_name='Movimientos_Combinados')
                
            st.download_button(
                label="📥 Descargar Reporte Mensual Consolidado (Excel)",
                data=output.getvalue(),
                file_name=f"Reporte_Consolidado_{mes_seleccionado}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Mostrar Resumen en Pantalla
            tab_egresos, tab_ingresos = st.tabs(["🔴 EGRESOS CONSOLIDADOS", "🟢 INGRESOS CONSOLIDADOS"])
            
            with tab_egresos:
                if df_egresos.empty:
                    st.info("Sin egresos.")
                else:
                    for _, row in df_egresos.iterrows():
                        concepto = row['concepto_agrupador']
                        total = row['importe']
                        st.markdown(f"**{concepto}** | Total Consolidado: `$ {total:,.2f}`")
                        
            with tab_ingresos:
                if df_ingresos.empty:
                    st.info("Sin ingresos.")
                else:
                    for _, row in df_ingresos.iterrows():
                        concepto = row['concepto_agrupador']
                        total = row['importe']
                        st.markdown(f"**{concepto}** | Total Consolidado: `$ {total:,.2f}`")

        except Exception as e:
            st.error(f"Error al cargar reportes: {str(e)}")

if __name__ == "__main__":
    main()
