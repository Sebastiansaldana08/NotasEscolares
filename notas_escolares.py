import os
import io
import tempfile
import pandas as pd
import streamlit as st
import time
import base64
from notas import procesar_pdf, escolar_o_egresado, calcular_promedios, cumple_excepcion, evaluar_periodos, procesar

# Especificar la ruta de Ghostscript
os.environ["PATH"] += os.pathsep + r'/usr/bin'

# creamos un directorio temporal
TEMP = tempfile.TemporaryDirectory()

@st.cache_data(persist="disk", show_spinner="Procesando ⏳")
def procesar_archivo(file, minADA, carrera):
    global TEMP
    dni, nombre, documento, df = procesar_pdf(file, pwd=TEMP.name)
    if isinstance(dni, str) and "No cumple con el requisito" in dni:
        return dni, None, None, None, None, None
    tipo = escolar_o_egresado(df)
    prom1a4, prom1a5, notaR = calcular_promedios(df)
    cumple, counts = cumple_excepcion(df, minADA)
    es_letras = df['NOTA'].apply(lambda x: not (isinstance(x, (int, float)) or str(x).isdigit())).any()
    periodos_resultados = evaluar_periodos(df, carrera, es_letras)
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

def main():
    st.set_page_config(initial_sidebar_state='collapsed', page_title="Sistema de Evaluación de Notas - UPCH", page_icon=":mortar_board:")
    
    # Obtener la ruta del directorio actual
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Ruta al logo
    logo_path = os.path.join(current_dir, "logo-upch.png")
    
    # Cargar el logo y convertir a base64
    with open(logo_path, "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()
    
    # Usar HTML para título y logo
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{encoded_logo}" width="80" style="margin-right: 20px;">
            <h1 style="margin: 0; font-size: 2em;">Sistema de Evaluación de Notas - UPCH</h1>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        ### Modalidad FACTOR EXCELENCIA
        Este sistema está diseñado para evaluar si los estudiantes aplican a la modalidad de admisión "FACTOR EXCELENCIA".
        Para aplicar, los estudiantes deben cumplir con los siguientes requisitos:
        - Haber obtenido un promedio de 14 o más o estar en el tercio superior del colegio de procedencia.
        - El promedio o cálculo del tercio superior se puede realizar usando los siguientes años académicos:
            - Del 1° al 4° de secundaria
            - De 1° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.
            - De 3° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.
        - Los postulantes que alcanzaron una vacante por esta modalidad deberán entregar a la OAMRA los siguientes documentos:
            - Certificado de estudios original del 1° al 5° año de secundaria.
            - Constancia emitida por la dirección del colegio de tener promedio igual o mayor a 14 en los años académicos 3°, 4° y 5° año de secundaria o estar en el tercio superior.
        """)
    
    with st.sidebar:
        minADA = 72
        min = st.select_slider(
            'Cantidad mínima de AD y A para aprobar:',
            options=range(1, 89),
            value=72,
            help='Cambiar el valor reprocesará todos los archivos actualmente cargados, se recomienda hacerlo antes de la carga de archivos'
        )
        btn = st.button("Aplicar")
        if btn:
            minADA = min
    carrera = st.selectbox('Selecciona la carrera:', ['MEDICINA', 'Todas las carreras, excepto MEDICINA'])
    
    files = st.file_uploader('Archivo PDF COE o CLA:', accept_multiple_files=True)
    if not files:
        return
    progress_bar = st.progress(0, text="Procesando archivos...")
    results = pd.DataFrame()  # resultados finales
    resultsData = pd.DataFrame()  # Tidy data
    resultsCount = pd.DataFrame()  # Cantidad de notas
    resultsR = pd.DataFrame()  # Promedios por areas
    resultsColegios = pd.DataFrame()  # Colegios por grados
    errores = pd.DataFrame()
    n = len(files)
    last_result = None  # Variable para almacenar el resultado del último archivo procesado
    last_dni = None  # Variable para almacenar el DNI del último archivo procesado
    for i, file in enumerate(files):
        progress_bar.progress((i + 1) / n, f"Procesando archivo {i + 1}...")
        try:
            result, data, count, notaR, periodos, es_letras = procesar_archivo(file, minADA, carrera)
            if isinstance(result, str):
                st.error(result)
                continue
            results = pd.concat([results, result.to_frame().T], axis=0, ignore_index=True)
            resultsData = pd.concat([resultsData, data], axis=0, ignore_index=True)
            resultsCount = pd.concat([resultsCount, count], axis=0, ignore_index=True)
            resultsR = pd.concat([resultsR, notaR], axis=0, ignore_index=True)
            resultsColegios = pd.concat([resultsColegios, periodos], axis=0, ignore_index=True)
            last_result = periodos  # Actualizar el último resultado
            last_dni = result['DNI']  # Actualizar el último DNI
        except Exception as e:
            errores = pd.concat(
                [errores, pd.DataFrame([[file.name, str(e)]], columns=['Archivo', 'Error'])],
                ignore_index=True
            )
            continue

    progress_bar.empty()
    
    res, cal, tab, err = st.tabs(['Resultados', 'Cálculos', 'Tablas', 'Errores'])
    if not results.empty:
        results = results.set_index('DNI')
        resultsData['NOTA'] = resultsData['NOTA'].map(lambda x: float(x) if str(x).isdigit() else x)
        dni_options = results.index.unique().tolist()
        dni = st.selectbox("Filtrar DNI:", options=dni_options, index=dni_options.index(last_dni) if last_dni in dni_options else 0)
        with res:
            st.dataframe(results.loc[[dni]].drop(columns='MinADyA'), use_container_width=True)
            st.write("Resultados por Periodo:")
            periodos_filtrados = resultsColegios[resultsColegios['DNI'] == dni]
            if not periodos_filtrados.empty:
                st.dataframe(periodos_filtrados.drop(columns='DNI').reset_index(drop=True))
            else:
                st.write("No hay resultados para mostrar.")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer:
                results.to_excel(writer)
            st.download_button("Descargar", data=buffer, file_name="Resultado.xlsx", mime="application/vnd.ms-excel")
        with cal:
            if 'GRADO' in resultsColegios.columns:
                st.dataframe(resultsColegios.query(f'DNI == "{dni}"').drop(columns='DNI').set_index('GRADO'))
            else:
                st.write("No se encontró la columna 'GRADO' en los resultados.")
            if 'NOTA' in resultsCount.columns:
                st.dataframe(resultsCount.query(f'DNI == "{dni}"').drop(columns='DNI').set_index('NOTA').T)
            else:
                st.write("No se encontró la columna 'NOTA' en los resultados.")
            prom = resultsR.query(f'DNI == "{dni}"').pivot(index=['DESC'], columns='GRADO', values='NOTA')
            st.dataframe(pd.concat([
                prom,
                prom.mean().rename('**PROMEDIO**').to_frame().T,
                prom.count().rename('**CANTIDAD**').to_frame().T
            ]).round(2), use_container_width=True)
        with tab:
            d = resultsData.query(f'DNI == "{dni}"').drop(columns='DNI')
            st.dataframe(
                d[d['COMP'].isnull()].pivot(
                    index=['DESC'], columns='GRADO', values='NOTA'
                ),
                use_container_width=True
            )
            st.dataframe(
                d[d['COMP'].notnull()].pivot(
                    index=['DESC', 'COMP'], columns='GRADO', values='NOTA'
                ),
                use_container_width=True
            )
    if errores.empty:
        with err:
            st.write("No se encontraron errores")
    else:
        with err:
            st.dataframe(errores, use_container_width=True)
        with res:
            st.error(f'Hay {errores.shape[0]} archivo(s) con error!')

if __name__ == '__main__':
    main()

