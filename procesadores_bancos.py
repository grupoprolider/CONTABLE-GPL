import pandas as pd
import numpy as np

def clean_amount(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).strip()
    if not val:
        return 0.0
    is_negative = False
    if val.startswith('(') and val.endswith(')'):
        is_negative = True
        val = val[1:-1]
    elif val.startswith('-'):
        is_negative = True
        val = val[1:]
    val = val.replace('$', '').replace(' ', '')
    if ',' in val and '.' in val:
        if val.rfind(',') > val.rfind('.'):
            val = val.replace('.', '').replace(',', '.')
        else:
            val = val.replace(',', '')
    elif ',' in val:
        val = val.replace(',', '.')
    try:
        num = float(val)
        return -num if is_negative else num
    except:
        return 0.0

def find_header_row(df, expected_columns):
    expected_set = set([str(x).lower() for x in expected_columns])
    for i in range(min(20, len(df))):
        row_values = [str(x).lower().strip() for x in df.iloc[i].values if not pd.isna(x)]
        matches = len(set(row_values).intersection(expected_set))
        if matches >= 2:
            return i
    return -1

def read_and_skip_header(file, expected_columns):
    df_raw = pd.read_excel(file, header=None)
    header_idx = find_header_row(df_raw, expected_columns)
    if header_idx != -1:
        df = pd.read_excel(file, header=header_idx)
    else:
        df = pd.read_excel(file)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def unificar_conceptos(concepto):
    """Unifica conceptos similares para que agrupen juntos."""
    c = str(concepto).upper().strip()
    if c.startswith('TRANSF') or c.startswith('TRF ') or c.startswith('TRANSFERENCIA'):
        return 'TRANSFERENCIAS'
    if 'RET. ING. BRUTOS' in c or 'RET ING BRUTOS' in c or 'IIBB' in c:
        return 'RETENCIONES / ACREDITACIONES INGRESOS BRUTOS'
    if 'SIRCREB' in c:
        return 'RETENCIONES SIRCREB'
    if 'DBCR 25413' in c or 'IMP. LEY 25413' in c or 'IMPUESTO DEBITOS' in c:
        return 'IMPUESTO LEY 25413 (DÉBITOS Y CRÉDITOS)'
    if 'CONV: 89615' in c:
        return 'RECAUDACIONES CONVENIO 89615'
    if 'REINTEGROS' in c:
        return 'REINTEGROS'
    if 'EXTRACCION CAJERO' in c:
        return 'EXTRACCIÓN CAJERO AUTOMÁTICO'
    if 'CHEQUE P/CAMARA' in c or 'CHEQUE P/CAMARA' in c:
        return 'CHEQUE POR CÁMARA'
    if 'DEBITOS REVERSOS' in c:
        return 'DÉBITOS REVERSOS SNP'
    if 'CR.RECAUD' in c or 'REC.DB.AUT' in c:
        return 'RECAUDACIONES Y DÉBITOS AUTOMÁTICOS'
    if 'SOL.RESC' in c or 'SOL. RESC' in c:
        return 'SOLICITUD DE RESCATE (FONDOS)'
    if 'LIQ.SUSC' in c or 'LIQ. SUSC' in c:
        return 'LIQUIDACIÓN DE SUSCRIPCIÓN (FONDOS)'
    if 'LIQ COMER PAYWAY' in c or 'PAYWAY' in c:
        return 'LIQUIDACIONES PAYWAY'
    if 'REV-ID:' in c:
        return 'REVERSOS Y DEVOLUCIONES'
    if 'CONV: 89440' in c or 'CONV: 89615' in c:
        if 'GRAVAMENES' in c:
            return 'RECAUDACIONES CONVENIO (GRAVÁMENES)'
        if 'COMISION' in c:
            return 'RECAUDACIONES CONVENIO (COMISIONES)'
        return 'RECAUDACIONES CONVENIO'
    if 'OG-DEBITO' in c and 'HABERES' in c:
        return 'OG-DEBITO HABERES'
    if c.startswith('IMPUESTO LEY'):
        # Para agrupar todos los 'IMPUESTO LEY dd/mm/aa 00001' de Francés
        return 'IMPUESTO LEY 25413 (DÉBITOS Y CRÉDITOS)'
    if c.startswith('COM.MANT.PQ'):
        return 'COMISIÓN MANTENIMIENTO PAQUETE'
    return concepto

def procesar_macro(file):
    df = read_and_skip_header(file, ['Fecha', 'Concepto', 'Importe'])
    df_res = df[['Fecha', 'Concepto', 'Importe']].copy()
    df_res.dropna(subset=['Concepto', 'Importe'], inplace=True, how='all')
    df_res['Importe'] = df_res['Importe'].apply(clean_amount)
    
    df_res['Detalle_Original'] = df_res['Concepto']
    df_res['Concepto_Agrupador'] = df_res['Concepto'].apply(unificar_conceptos)
    df_res.drop(columns=['Concepto'], inplace=True)
    return df_res

def procesar_supervielle(file):
    df = read_and_skip_header(file, ['Fecha', 'Concepto', 'Débito', 'Crédito'])
    col_debito = 'Débito' if 'Débito' in df.columns else 'Debito'
    col_credito = 'Crédito' if 'Crédito' in df.columns else 'Credito'
    
    df_res = df[['Fecha', 'Concepto', col_debito, col_credito]].copy()
    if 'Detalle' in df.columns:
        df_res['Detalle_Adicional'] = df['Detalle']
    
    df_res.dropna(subset=['Concepto'], inplace=True)
    df_res[col_debito] = df_res[col_debito].apply(clean_amount)
    df_res[col_credito] = df_res[col_credito].apply(clean_amount)
    df_res['Importe'] = df_res[col_credito].fillna(0) - df_res[col_debito].fillna(0).abs()
    
    # Combinar Concepto y Detalle para el original si existe
    if 'Detalle_Adicional' in df_res.columns:
        df_res['Detalle_Original'] = df_res['Concepto'].astype(str) + " - " + df_res['Detalle_Adicional'].fillna('').astype(str)
        df_res.drop(columns=['Detalle_Adicional'], inplace=True)
    else:
        df_res['Detalle_Original'] = df_res['Concepto']
        
    df_res['Concepto_Agrupador'] = df_res['Concepto'].apply(unificar_conceptos)
    df_res.drop(columns=['Concepto', col_debito, col_credito], inplace=True)
    return df_res

def procesar_santa_fe(file):
    df = read_and_skip_header(file, ['Fecha', 'Concepto', 'Débito', 'Crédito'])
    col_debito = 'Débito' if 'Débito' in df.columns else 'Debito'
    col_credito = 'Crédito' if 'Crédito' in df.columns else 'Credito'
    
    df_res = df[['Fecha', 'Concepto', col_debito, col_credito]].copy()
    df_res.dropna(subset=['Concepto'], inplace=True)
    df_res[col_debito] = df_res[col_debito].apply(clean_amount)
    df_res[col_credito] = df_res[col_credito].apply(clean_amount)
    df_res['Importe'] = df_res[col_credito].fillna(0) - df_res[col_debito].fillna(0).abs()
    
    df_res['Detalle_Original'] = df_res['Concepto']
    df_res['Concepto_Agrupador'] = df_res['Concepto'].apply(unificar_conceptos)
    df_res.drop(columns=['Concepto', col_debito, col_credito], inplace=True)
    return df_res

def procesar_industrial(file):
    df_raw = pd.read_excel(file, header=None)
    
    # Intentar encontrar la fila de encabezado buscando distintas combinaciones típicas
    header_idx = find_header_row(df_raw, ['Fecha Val', 'Descripción', 'Importe'])
    if header_idx == -1:
        header_idx = find_header_row(df_raw, ['FECHA', 'DESCRIPCION_MOV', 'IMPORTE'])
    if header_idx == -1:
        header_idx = find_header_row(df_raw, ['Fecha', 'Concepto', 'Importe'])
        
    if header_idx != -1:
        df = pd.read_excel(file, header=header_idx)
    else:
        df = pd.read_excel(file)
        
    df.columns = [str(c).strip() for c in df.columns]
    
    # Crear un diccionario para buscar columnas sin importar mayúsculas o minúsculas
    cols_upper = {c.upper(): c for c in df.columns}
    
    if 'FECHA VALOR' in cols_upper: col_fecha = cols_upper['FECHA VALOR']
    elif 'FECHA VAL' in cols_upper: col_fecha = cols_upper['FECHA VAL']
    elif 'FECHA OPERACIÓN' in cols_upper: col_fecha = cols_upper['FECHA OPERACIÓN']
    elif 'FECHA OPERACION' in cols_upper: col_fecha = cols_upper['FECHA OPERACION']
    elif 'FECHA OPER' in cols_upper: col_fecha = cols_upper['FECHA OPER']
    elif 'FECHA' in cols_upper: col_fecha = cols_upper['FECHA']
    else: raise ValueError(f"No se encontró columna de Fecha. Columnas: {list(df.columns)}")
    
    if 'DESCRIPCIÓN' in cols_upper: col_concepto = cols_upper['DESCRIPCIÓN']
    elif 'DESCRIPCION' in cols_upper: col_concepto = cols_upper['DESCRIPCION']
    elif 'DESCRIPCION_MOV' in cols_upper: col_concepto = cols_upper['DESCRIPCION_MOV']
    elif 'CONCEPTO' in cols_upper: col_concepto = cols_upper['CONCEPTO']
    else: raise ValueError(f"No se encontró columna de Concepto. Columnas: {list(df.columns)}")
    
    if 'IMPORTE' in cols_upper: col_importe = cols_upper['IMPORTE']
    else: raise ValueError(f"No se encontró columna de Importe. Columnas: {list(df.columns)}")

    df_res = df[[col_fecha, col_concepto, col_importe]].copy()
    
    if 'DETALLE' in cols_upper:
        df_res['Detalle_Adicional'] = df[cols_upper['DETALLE']]
        
    df_res.dropna(subset=[col_concepto], inplace=True)
    df_res[col_importe] = df_res[col_importe].apply(clean_amount)
    
    if 'Detalle_Adicional' in df_res.columns:
        df_res['Detalle_Original'] = df_res[col_concepto].astype(str) + " - " + df_res['Detalle_Adicional'].fillna('').astype(str)
        df_res.drop(columns=['Detalle_Adicional'], inplace=True)
    else:
        df_res['Detalle_Original'] = df_res[col_concepto]
        
    df_res['Concepto_Agrupador'] = df_res[col_concepto].apply(unificar_conceptos)
    df_res.rename(columns={col_fecha: 'Fecha', col_importe: 'Importe'}, inplace=True)
    df_res.drop(columns=[col_concepto], inplace=True)
    return df_res

def procesar_frances(file):
    df_raw = pd.read_excel(file, header=None)
    
    header_idx = find_header_row(df_raw, ['Fecha', 'Concepto', 'Crédito', 'Débito'])
    if header_idx != -1:
        df = pd.read_excel(file, header=header_idx)
    else:
        df = pd.read_excel(file)
        
    df.columns = [str(c).strip() for c in df.columns]
    cols_upper = {c.upper(): c for c in df.columns}
    
    if 'FECHA' in cols_upper: col_fecha = cols_upper['FECHA']
    elif 'FECHA VALOR' in cols_upper: col_fecha = cols_upper['FECHA VALOR']
    else: raise ValueError(f"No se encontró columna de Fecha. Columnas: {list(df.columns)}")
    
    if 'CONCEPTO' in cols_upper: col_concepto = cols_upper['CONCEPTO']
    elif 'DESCRIPCIÓN' in cols_upper: col_concepto = cols_upper['DESCRIPCIÓN']
    else: raise ValueError(f"No se encontró columna de Concepto. Columnas: {list(df.columns)}")
    
    if 'DÉBITO' in cols_upper: col_debito = cols_upper['DÉBITO']
    elif 'DEBITO' in cols_upper: col_debito = cols_upper['DEBITO']
    else: raise ValueError("Falta columna Débito en Francés.")
    
    if 'CRÉDITO' in cols_upper: col_credito = cols_upper['CRÉDITO']
    elif 'CREDITO' in cols_upper: col_credito = cols_upper['CREDITO']
    else: raise ValueError("Falta columna Crédito en Francés.")

    df_res = df[[col_fecha, col_concepto, col_debito, col_credito]].copy()
    
    if 'DETALLE' in cols_upper:
        df_res['Detalle_Adicional'] = df[cols_upper['DETALLE']]
        
    df_res.dropna(subset=[col_concepto], inplace=True)
    df_res[col_debito] = df_res[col_debito].apply(clean_amount)
    df_res[col_credito] = df_res[col_credito].apply(clean_amount)
    df_res['Importe'] = df_res[col_credito].fillna(0) - df_res[col_debito].fillna(0).abs()
    
    if 'Detalle_Adicional' in df_res.columns:
        df_res['Detalle_Original'] = df_res[col_concepto].astype(str) + " - " + df_res['Detalle_Adicional'].fillna('').astype(str)
        df_res.drop(columns=['Detalle_Adicional'], inplace=True)
    else:
        df_res['Detalle_Original'] = df_res[col_concepto]
        
    df_res['Concepto_Agrupador'] = df_res[col_concepto].apply(unificar_conceptos)
    df_res.rename(columns={col_fecha: 'Fecha'}, inplace=True)
    df_res.drop(columns=[col_concepto, col_debito, col_credito], inplace=True)
    return df_res

def procesar_galicia(file):
    df_raw = pd.read_excel(file, header=None)
    
    header_idx = find_header_row(df_raw, ['Fecha', 'Descripción', 'Débitos', 'Créditos'])
    if header_idx != -1:
        df = pd.read_excel(file, header=header_idx)
    else:
        df = pd.read_excel(file)
        
    df.columns = [str(c).strip() for c in df.columns]
    cols_upper = {c.upper(): c for c in df.columns}
    
    # Check if it is the old format (Importe) or new format (Débitos/Créditos)
    if 'IMPORTE' in cols_upper:
        return procesar_industrial(file)
        
    if 'FECHA' in cols_upper: col_fecha = cols_upper['FECHA']
    else: raise ValueError("No se encontró columna de Fecha en Galicia.")
    
    if 'DESCRIPCIÓN' in cols_upper: col_concepto = cols_upper['DESCRIPCIÓN']
    elif 'DESCRIPCION' in cols_upper: col_concepto = cols_upper['DESCRIPCION']
    elif 'CONCEPTO' in cols_upper: col_concepto = cols_upper['CONCEPTO']
    else: raise ValueError("No se encontró columna de Concepto en Galicia.")
    
    if 'DÉBITOS' in cols_upper: col_debito = cols_upper['DÉBITOS']
    elif 'DEBITOS' in cols_upper: col_debito = cols_upper['DEBITOS']
    elif 'DÉBITO' in cols_upper: col_debito = cols_upper['DÉBITO']
    elif 'DEBITO' in cols_upper: col_debito = cols_upper['DEBITO']
    else: raise ValueError("Falta columna Débitos en Galicia.")
    
    if 'CRÉDITOS' in cols_upper: col_credito = cols_upper['CRÉDITOS']
    elif 'CREDITOS' in cols_upper: col_credito = cols_upper['CREDITOS']
    elif 'CRÉDITO' in cols_upper: col_credito = cols_upper['CRÉDITO']
    elif 'CREDITO' in cols_upper: col_credito = cols_upper['CREDITO']
    else: raise ValueError("Falta columna Créditos en Galicia.")

    df_res = df[[col_fecha, col_concepto, col_debito, col_credito]].copy()
    
    # Try to grab extra details if they exist in Galicia
    detalles_extra = []
    for extra_col in ['CONCEPTO', 'OBSERVACIONES CLIENTE', 'LEYENDAS ADICIONALES 1']:
        if extra_col in cols_upper:
            detalles_extra.append(df[cols_upper[extra_col]].fillna('').astype(str))
            
    df_res.dropna(subset=[col_concepto], inplace=True)
    df_res[col_debito] = df_res[col_debito].apply(clean_amount)
    df_res[col_credito] = df_res[col_credito].apply(clean_amount)
    df_res['Importe'] = df_res[col_credito].fillna(0) - df_res[col_debito].fillna(0).abs()
    
    if detalles_extra:
        combined_detail = df_res[col_concepto].astype(str)
        for extra in detalles_extra:
            combined_detail = combined_detail + " - " + extra
        df_res['Detalle_Original'] = combined_detail
    else:
        df_res['Detalle_Original'] = df_res[col_concepto]
        
    df_res['Concepto_Agrupador'] = df_res[col_concepto].apply(unificar_conceptos)
    df_res.rename(columns={col_fecha: 'Fecha'}, inplace=True)
    df_res.drop(columns=[col_concepto, col_debito, col_credito], inplace=True)
    return df_res

PROCESADORES = {
    'Macro': procesar_macro,
    'Supervielle': procesar_supervielle,
    'Santa Fe': procesar_santa_fe,
    'Industrial': procesar_industrial,
    'Galicia': procesar_galicia,
    'Francés': procesar_frances
}
