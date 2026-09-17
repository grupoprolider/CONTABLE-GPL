import streamlit as st
import pandas as pd
import io
from procesadores_bancos import PROCESADORES

st.set_page_config(page_title="Asientos Contables Bancarios", page_icon="🏦", layout="wide")

def main():
    # Inyectar CSS personalizado para mejorar el aspecto
    st.markdown("""
        <style>
        /* Hacer la letra de los desplegables más grande y negrita */
        div[data-testid="stExpander"] details summary p {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            color: #1f2937 !important;
        }
        /* Darle un fondo sutil a la barra del desplegable para que resalte */
        div[data-testid="stExpander"] details summary {
            background-color: #f3f4f6;
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
        }
        /* Ajustar el ancho máximo para que no quede tan estirado en pantallas grandes */
        .block-container {
            max-width: 1200px;
        }
        </style>
    """, unsafe_allow_html=True)
    
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
                # Procesar según el banco seleccionado
                funcion_procesar = PROCESADORES[banco_seleccionado]
                df = funcion_procesar(uploaded_file)
                
            # Asegurar formato de fecha (dayfirst=True para que 02/09 sea 2 de septiembre)
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce', dayfirst=True)
            
            st.success("Archivo procesado exitosamente!")
            
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

if __name__ == "__main__":
    main()
