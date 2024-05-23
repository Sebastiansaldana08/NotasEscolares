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
    gs = shutil.which("gs")
    if not gs:
        raise RuntimeError("Ghostscript not found")
    subprocess.check_call(
        [gs,"-dSAFER","-dNOPAUSE","-dBATCH",
         "-sDEVICE=pdfwrite","-o",out_file,in_file,],
        stdout= subprocess.DEVNULL,
        stderr= subprocess.DEVNULL
    )

def read_data(filepath):
    reader = PdfReader(filepath,strict=True)
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
        nombre = re.findall(r'estudiante(?:\s)*(.*),(?:\s)*con',text)
    elif certificado:
        documento = certificado[0]
        nombre = re.findall(r'Que(?:\s)*(.*),(?:\s)*con DNI',text)
    else:
        raise RuntimeError('EL archivo no es ni COE ni CLAE')    
    if nombre:
        nombre = nombre[0]
    else:
        nombre = ''
    documento = ' '.join(documento.split())
    dni = re.findall(
        r'DNI(?:\s)*?(?: del estudiante)?(?:\s)*?N\.°(?:\s)*?([0-9]{8})',
        text
    )
    if dni:
        dni = dni[0]
    else:
        raise RuntimeError("No se encontró el DNI")

    return dni,nombre,documento

def procesar_tabla(tab):
    # Quitamos la última columna de Observación si es que hubiera
    if tab.iloc[0,-1] == 'Observación':
        tab = tab.iloc[:,:-1]
    # creamos la cabecera
    header = tab.iloc[:3].apply(lambda x: x.replace('',x.name))
    tab.columns = pd.MultiIndex.from_arrays(header.values)
    tab = tab.iloc[3:-1] # se quitan los 3 primeros y el ultimo
    # Rellenar los 2 primeros campos hacia abajo
    tab.iloc[:,:2] = tab.iloc[:,:2].replace('',np.nan).ffill()
    # Convertir a formato TidyData
    tab = (tab.melt(id_vars=list(tab.columns[:-5]))
           .rename(columns={
               ('Año lectivo:','Grado:','Código modular de la IE:'):'TIPO',
               (1,1,1):'DESC',
               (2,2,2):'COMP',
               'variable_0':'AÑO',
               'variable_1':'GRADO',
               'variable_2':'CODMOD',
               'value':'NOTA',
               })
           .query('NOTA != "-"') # Quitar las filas sin nota
           .query('NOTA != "EXO"') # Quitar los cursos exonerados
           )
    return tab

def procesar_pdf(file,pwd=os.getcwd()):
    filename = f'{pwd}/file.pdf'
    with open(filename,'wb') as f:
        f.write(file.getbuffer())

    # Reparamos el pdf para que sea estándar
    original = f'{filename[:-4]}_old{filename[-4:]}'
    os.rename(filename,original)
    repair_pdf(original,filename)

    # Buscamos el DNI y si es COE o CLA
    dni,nombre,documento = read_data(filename)

    # Obtener la tabla de cada hoja del PDF
    tables = camelot.read_pdf(filename,pages='all',strip_text='\n')
    tablas = []
    l = []
    for t in tables:
        d = t.df
        # Ignorar tabla de "pie de página"
        if d.iloc[-1,0].startswith('* Este'):
            continue
        # Quitar la cabecera si NO ES la primera tabla
        if len(l) > 0:
            d = d.iloc[3:]
        l.append(d)
        # Si es la última tabla
        if d.iloc[-1,0] == 'Situación final': 
            tablas.append(procesar_tabla(pd.concat(l)))
            l = []
    res = pd.concat(tablas)
    res['DNI'] = dni
    res['DOCUMENTO'] = documento
    res['TIPO'] = res['TIPO'].str.replace(' y Competencias','')
    res['COMP'] = res['COMP'].replace('',np.nan)
    res= res.query('TIPO == "Áreas Curriculares"')
    # Fix Educación Religiosa
    res.loc[
        res['DESC'].str.startswith('EDUCACIÓN RELIGIOSA Construye'),'DESC'
    ] = 'EDUCACIÓN RELIGIOSA'
    res.loc[
        res['COMP'].fillna('').str.startswith('trascendente, comprendiendo'),'COMP'
    ] = 'Construye su identidad como persona humana, amada por Dios, digna, libre y trascendente, comprendiendo la doctrina de su propia religión, abierto al diálogo con las que le son cercanas'
    # Fix Ciencia y Tecnología
    res.loc[
        res['COMP'].fillna('').str.contains('vivos; materia'),'COMP'
    ] = 'Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía, biodiversidad, Tierra y universo'
    return dni,nombre,documento,res

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
    # Contar el número de notas AD y A
    counts = df['NOTA'].value_counts()
    num_ad = counts.get('AD', 0)
    num_a = counts.get('A', 0)
    total_notas = len(df)

    # Calcular el porcentaje de notas AD y A
    porcentaje = ((num_ad + num_a) / total_notas) * 100

    # Determinar si el estudiante aplica a la modalidad
    aplica = porcentaje >= 90

    # Estructura de resultados
    resultado = 'Sí' if aplica else 'No'
    counts = counts.reset_index().rename(columns={'index': 'NOTA', 'NOTA': 'Cantidad'})
    counts['DNI'] = df['DNI'].unique()[0]

    return resultado, counts

def calcular_promedios(df):
    # Convertimos la nota del comportamiento a número
    comportamiento = {'AD': 20, 'A': 17, 'B': 15, 'C': 13}
    df.loc[
        df['DESC'] == 'COMPORTAMIENTO', 'NOTA'
    ] = (df
         .loc[df['DESC'] == 'COMPORTAMIENTO', 'NOTA']
         .map(lambda x: comportamiento[x]))
    # Separamos grados con letras y grados con números
    numeros = df[df['NOTA'].astype(str).str.isdigit()]
    numeros['NOTA'] = numeros['NOTA'].astype(float)
    letras = df[~df['NOTA'].astype(str).str.isdigit()]
    # Calculamos la nota R para las letras
    equiv = {'AD': 4.0, 'A': 3.0, 'B': 2.5, 'C': 1.0}
    letras['NOTA'] = letras['NOTA'].apply(lambda x: equiv[x])
    # Se obtiene la nota R por Competencia
    Rnumeros = numeros.groupby(['DNI', 'GRADO', 'DESC'])['NOTA'].mean()
    Rletras = (letras
               .groupby(['DNI', 'GRADO', 'DESC'], group_keys=False)['NOTA']
               .apply(lambda x: ((x.sum() / x.count()) * 10 / 4) * 1000)
               .map(math.trunc) / 1000)
    # Se obtiene la nota vigesimal
    Rletras = ((Rletras - 2.5) * 8 / 3)
    # Se vuelve a juntar los grados
    if Rletras.empty:
        notaR = Rnumeros
    elif Rnumeros.empty:
        notaR = Rletras
    else:
        notaR = pd.DataFrame(pd.concat([Rnumeros, Rletras]))
    notaR = notaR.reset_index()
    # Se obtiene el promedio por Grado
    if '5.°' in notaR['GRADO'].unique():
        prom1a5 = notaR['NOTA'].mean()
    else:
        prom1a5 = None
    prom1a4 = notaR.loc[~notaR['GRADO'].isin(['5.°']), 'NOTA'].mean()
    return prom1a4, prom1a5, notaR

def evaluar_periodos(df):
    periodos = {
        "1RO A 4TO": df[df['GRADO'].isin(['1.°', '2.°', '3.°', '4.°'])],
        "1RO A 5TO": df[df['GRADO'].isin(['1.°', '2.°', '3.°', '4.°', '5.°'])],
        "3RO A 5TO": df[df['GRADO'].isin(['3.°', '4.°', '5.°'])]
    }

    evaluaciones = []
    for periodo, data in periodos.items():
        num_ad = data['NOTA'].value_counts().get('AD', 0)
        num_a = data['NOTA'].value_counts().get('A', 0)
        total_notas = len(data)
        porcentaje = ((num_ad + num_a) / total_notas) * 100
        estado = "SI CUMPLE" if porcentaje >= 90 else "NO CUMPLE"
        evaluaciones.append({
            "PERIODO": periodo,
            "PORCENTAJE": f"{porcentaje:.2f}%",
            "ESTADO": estado
        })

    return pd.DataFrame(evaluaciones)

