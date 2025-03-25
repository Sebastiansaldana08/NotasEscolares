import os
import re
import math
import shutil
import subprocess
import camelot
import numpy as np
import pandas as pd
from pypdf import PdfReader

def repair_pdf(in_file, out_file):
    possible_paths = [
        shutil.which("gswin64c"),
        shutil.which("gswin32c"),
        shutil.which("gs"),
        r"C:\Program Files\gs\gs10.03.1\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.03.1\bin\gswin32c.exe",
        "/usr/bin/gs",
        "/usr/local/bin/gs",
        "/app/.heroku/vendor/bin/gs"
    ]
    
    gs = next((path for path in possible_paths if path and os.path.exists(path)), None)
    
    if not gs:
        raise RuntimeError("[ERROR] Ghostscript no encontrado en las rutas especificadas")
    
    subprocess.check_call(
        [gs, "-dSAFER", "-dNOPAUSE", "-dBATCH",
         "-sDEVICE=pdfwrite", "-o", out_file, in_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def read_data(filepath):
    reader = PdfReader(filepath, strict=True)
    first_page = reader.pages[0]
    text = first_page.extract_text()

    constancia = re.findall(
        r'CONSTANCIA(?:\s)*DE(?:\s)*LOGROS(?:\s)*DE(?:\s)*APRENDIZAJE',
        text
    )
    certificado = re.findall(
        r'CERTIFICADO(?:\s)*OFICIAL(?:\s)*DE(?:\s)*ESTUDIOS',
        text
    )

    if constancia:
        documento = constancia[0]
        nombre = re.findall(r'estudiante(?:\s)(.),(?:\s)*con', text)
    elif certificado:
        documento = certificado[0]
        nombre = re.findall(r'Que(?:\s)(.),(?:\s)*con DNI', text)
    else:
        raise RuntimeError('El archivo no es ni COE ni CLAE')    
    
    if nombre:
        nombre = nombre[0]
    else:
        nombre = ''
        
    documento = ' '.join(documento.split())

    # Buscar DNI o código de estudiante
    dni = re.findall(
        r'DNI(?:\s)?(?: del estudiante)?(?:\s)?N\.°(?:\s)*?([0-9]{8})',
        text
    )
    
    if not dni:
        dni = re.findall(
            r'(?:código de estudiante|N\.°)(?:\s)*([0-9]{13,16})',  # Ajuste para manejar códigos de 13 a 16 dígitos
            text,
            re.IGNORECASE
        )
    
    if dni:
        dni = dni[0]
    else:
        raise ValueError("No se encontró el DNI o el código de estudiante")

    return dni, nombre, documento

def procesar_tabla(tab):
    if tab.iloc[0, -1] == 'Observación':
        tab = tab.iloc[:, :-1]
    header = tab.iloc[:3].apply(lambda x: x.replace('', x.name))
    tab.columns = pd.MultiIndex.from_arrays(header.values)
    tab = tab.iloc[3:-1]
    tab.iloc[:, :2] = tab.iloc[:, :2].replace('', np.nan).ffill()
    tab = (tab.melt(id_vars=list(tab.columns[:-5]))
           .rename(columns={
               ('Año lectivo:', 'Grado:', 'Código modular de la IE:'): 'TIPO',
               (1, 1, 1): 'DESC',
               (2, 2, 2): 'COMP',
               'variable_0': 'AÑO',
               'variable_1': 'GRADO',
               'variable_2': 'CODMOD',
               'value': 'NOTA',
           })
           .query('NOTA != "-"')
           .query('NOTA != "EXO"')
           )
    if 'COMP' not in tab.columns:
        tab['COMP'] = np.nan
    return tab

def verificar_anio_lectivo(df):
    anios = df['AÑO'].astype(int)
    if not anios.empty and anios.max() <= 2022:
        return False
    return True

def obtener_grado_maximo(df):
    grados = df['GRADO'].str.extract(r'(\d+)')[0].astype(int)
    return grados.max()

def procesar_pdf(file, pwd=os.getcwd()):
    filename = f'{pwd}/file.pdf'
    with open(filename, 'wb') as f:
        f.write(file.getbuffer())
    original = f'{filename[:-4]}_old{filename[-4:]}'
    os.rename(filename, original)
    repair_pdf(original, filename)
    dni, nombre, documento = read_data(filename)
    tables = camelot.read_pdf(filename, pages='all', strip_text='\n')
    tablas = []
    l = []
    for t in tables:
        d = t.df
        if d.iloc[-1, 0].startswith('* Este'):
            continue
        if len(l) > 0:
            d = d.iloc[3:]
        l.append(d)
        if d.iloc[-1, 0] == 'Situación final': 
            tablas.append(procesar_tabla(pd.concat(l)))
            l = []
    res = pd.concat(tablas)
    res['DNI'] = dni
    res['DOCUMENTO'] = documento
    res['TIPO'] = res['TIPO'].str.replace(' y Competencias', '')
    res['COMP'] = res['COMP'].replace('', np.nan)
    res = res.query('TIPO == "Áreas Curriculares"')
    res.loc[res['DESC'].str.startswith('EDUCACIÓN RELIGIOSA Construye'), 'DESC'] = 'EDUCACIÓN RELIGIOSA'
    res.loc[res['COMP'].fillna('').str.startswith('trascendente, comprendiendo'), 'COMP'] = 'Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente, comprendiendo la doctrina de su propia religión, abierto al diálogo con las que le son cercanas'
    res.loc[res['COMP'].fillna('').str.contains('vivos; materia'), 'COMP'] = 'Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo'
    
    # Verificar año lectivo del grado 4.° y 5.°
    if not verificar_anio_lectivo(res):
        return f"{dni} - No cumple con el requisito de tener hasta dos años de egreso.", None, None, None, None
    
    grado_maximo = obtener_grado_maximo(res)
    
    return dni, nombre, documento, res, grado_maximo

def escolar_o_egresado(df):
    grados = df['GRADO'].unique()
    if len(grados) == 5:
        tipo = 'Egresado'
    elif len(grados) == 4:
        tipo = 'Escolar'
    else:
        tipo = '-'
    return tipo

def cumple_excepcion(df, minADA):
    number = df['NOTA'].apply(lambda x: isinstance(x, (int, float)) or str(x).isdigit())
    mismo_colegio = len(df['CODMOD'].unique()) == 1
    if mismo_colegio:
        prom = df.loc[number, 'NOTA'].astype(float).mean()
    else:
        prom = df.loc[number & df['GRADO'].isin(['3.°', '4.°', '5.°']), 'NOTA'].astype(float).mean()
    counts = (df
              .loc[~number, 'NOTA']
              .value_counts()
              .rename('Cantidad')
              .to_frame()
              .reset_index()
              .rename(columns={'index': 'NOTA'}))
    counts['DNI'] = df['DNI'].unique()[0]
    if 'C' in df['NOTA']:
        return 'No', counts
    if number.sum() > (~number).sum():
        return 'Sí' if prom >= 14 else 'No', counts
    else:
        ad_y_a = df[~number & df['NOTA'].isin(['AD', 'A'])].shape[0]
        return 'Sí' if ad_y_a >= minADA else 'No', counts

def calcular_promedios(df):
    comportamiento = {'AD': 20, 'A': 17, 'B': 15, 'C': 13}
    df.loc[df['DESC'] == 'COMPORTAMIENTO', 'NOTA'] = (df.loc[df['DESC'] == 'COMPORTAMIENTO', 'NOTA'].map(lambda x: comportamiento[x] if isinstance(x, str) else x))
    numeros = df[df['NOTA'].apply(lambda x: isinstance(x, (int, float)) or str(x).isdigit())]
    numeros['NOTA'] = numeros['NOTA'].astype(float)
    letras = df[~df['NOTA'].apply(lambda x: isinstance(x, (int, float)) or str(x).isdigit())]
    equiv = {'AD': 4.0, 'A': 3.0, 'B': 2.5, 'C': 1.0}
    letras['NOTA'] = letras['NOTA'].apply(lambda x: equiv[x])
    Rnumeros = numeros.groupby(['DNI', 'GRADO', 'DESC'])['NOTA'].mean()
    Rletras = (letras.groupby(['DNI', 'GRADO', 'DESC'], group_keys=False)['NOTA'].apply(lambda x: ((x.sum() / x.count()) * 10 / 4) * 1000).map(math.trunc) / 1000)
    Rletras = ((Rletras - 2.5) * 8 / 3)
    if Rletras.empty:
        notaR = Rnumeros
    elif Rnumeros.empty:
        notaR = Rletras
    else:
        notaR = pd.DataFrame(pd.concat([Rnumeros, Rletras]))
    notaR = notaR.reset_index()
    if '5.°' in notaR['GRADO'].unique():
        prom1a5 = notaR['NOTA'].mean()
    else:
        prom1a5 = None
    prom1a4 = notaR.loc[~notaR['GRADO'].isin(['5.°']), 'NOTA'].mean()
    return prom1a4, prom1a5, notaR

def evaluar_periodos(df, carrera, es_letras, grado_maximo):
    periodos_todos = {
        "1RO A 4TO": ['1.°', '2.°', '3.°', '4.°'],
        "1RO A 5TO": ['1.°', '2.°', '3.°', '4.°', '5.°'],
        "3RO A 5TO": ['3.°', '4.°', '5.°']
    }
    periodos = {}
    if carrera == "MEDICINA":
        if grado_maximo == 4:
            periodos["1RO A 4TO"] = periodos_todos["1RO A 4TO"]
        elif grado_maximo == 5:
            periodos["1RO A 4TO"] = periodos_todos["1RO A 4TO"]
            periodos["1RO A 5TO"] = periodos_todos["1RO A 5TO"]
            periodos["3RO A 5TO"] = periodos_todos["3RO A 5TO"]
    else:
        if grado_maximo == 4:
            periodos["1RO A 4TO"] = periodos_todos["1RO A 4TO"]
        elif grado_maximo == 5:
            periodos["1RO A 4TO"] = periodos_todos["1RO A 4TO"]
            periodos["1RO A 5TO"] = periodos_todos["1RO A 5TO"]
            periodos["3RO A 5TO"] = periodos_todos["3RO A 5TO"]
    
    resultados = []
    for periodo, grados in periodos.items():
        notas = df[df['GRADO'].isin(grados)]
        if notas.empty:
            continue
        if es_letras:
            total_notas = len(notas)
            ad_a = len(notas[notas['NOTA'].isin(['AD', 'A'])])
            porcentaje_ad_a = (ad_a / total_notas) * 100 if total_notas > 0 else 0
            estado = "CUMPLE" if porcentaje_ad_a >= 90 else "NO CUMPLE"
            resultados.append({
                "PERIODO EVALUACIÓN": periodo,
                "PORCENTAJE CON NOTAS AD Y A": f"{porcentaje_ad_a:.2f}%",
                "ESTADO": estado
            })
        else:
            notas_numericas = notas['NOTA'].apply(lambda x: float(x) if isinstance(x, (int, float)) or str(x).isdigit() else None)
            notas_numericas = notas_numericas.dropna()
            promedio = notas_numericas.mean() if not notas_numericas.empty else None
            if carrera == "MEDICINA":
                estado = "CUMPLE" if promedio and promedio >= 16 else "NO CUMPLE"
            else:
                estado = "CUMPLE" if promedio and promedio >= 14 else "NO CUMPLE"
            resultados.append({
                "PERIODO EVALUACIÓN": periodo,
                "PROMEDIO FINAL": f"{promedio:.2f}" if promedio is not None else "N/A",
                "ESTADO": estado
            })
    return pd.DataFrame(resultados)

def procesar(file, minADA, carrera):
    global TEMP
    dni, nombre, documento, df, grado_maximo = procesar_pdf(file, pwd=TEMP.name)
    if isinstance(dni, str) and "No cumple con el requisito" in dni:
        return dni, None, None, None, None, None
    tipo = escolar_o_egresado(df)
    prom1a4, prom1a5, notaR = calcular_promedios(df)
    cumple, counts = cumple_excepcion(df, minADA)
    es_letras = df['NOTA'].apply(lambda x: not (isinstance(x, (int, float)) or str(x).isdigit())).any()
    periodos_resultados = evaluar_periodos(df, carrera, es_letras, grado_maximo)
    periodos_resultados['DNI'] = dni
    result = pd.Series({
        'DNI': dni,
        'Nombre': nombre,
        'Excepcion': cumple,
        'Prom1a4': prom1a4,
        'Prom1a5': prom1a5,
        'Tipo': tipo,
        'Documento': documento,
        'MinADyA': minADA,
    })
    notas = counts.drop(columns='DNI').set_index('NOTA')['Cantidad'].rename(0)
    result = pd.concat([result, notas], axis=0)
    result = result.reindex(['DNI', 'Nombre', 'Tipo', 'Excepcion', 'Prom1a4', 'Prom1a5', 'AD', 'A', 'B', 'C', 'Documento', 'MinADyA'])
    return result, df, counts, notaR, periodos_resultados, es_letras

