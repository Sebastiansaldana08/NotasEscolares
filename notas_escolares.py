import os
import io
import tempfile
import pandas as pd
import streamlit as st
import time
import base64
from notas import procesar_pdf, cumple_excepcion, calcular_promedios, escolar_o_egresado, evaluar_periodos

# Especificar la ruta de Ghostscript
os.environ["PATH"] += os.pathsep + r'/usr/bin'

# Crear un directorio temporal
TEMP = tempfile.TemporaryDirectory()

@st.cache_data(persist="disk", show_spinner="Procesando ⏳")
def procesar(file, minADA):
    # Se usa esta función para tener cache y no se recalcule
    global TEMP
    dni, nombre, documento, df = procesar_pdf(file, pwd=TEMP.name)
    tipo = escolar_o_egresado(df)
    prom1a4, prom1a5, notaR = calcular_promedios(df)
    cumple, counts = cumple_excepcion(df, minADA)
    periodos = evaluar_periodos(df)
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
    return result, df, counts, notaR, periodos

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
    files = st.file_uploader('Sube los archivos PDF COE o CLA:', accept_multiple_files=True)
    if not files:
        return
    progress_bar = st.progress(0, text="Procesando archivos...")
    results = pd.DataFrame()  # Resultados finales
    resultsData = pd.DataFrame()  # Tidy data
    resultsCount = pd.DataFrame()  # Cantidad de notas
    resultsR = pd.DataFrame()  # Promedios por áreas
    resultsPeriodos = pd.DataFrame()  # Evaluaciones por periodos
    errores = pd.DataFrame()
    n = len(files)
    for i, file in enumerate(files):
        progress_bar.progress((i+1)/n, f"Procesando archivo {i+1} de {n}...")
        try:
            result, data, count, notaR, periodos = procesar(file, minADA)
            results = pd.concat([results, result.to_frame().T], axis=0, ignore_index=True)
            resultsData = pd.concat([resultsData, data], axis=0, ignore_index=True)
            resultsCount = pd.concat([resultsCount, count], axis=0, ignore_index=True)
            resultsR = pd.concat([resultsR, notaR], axis=0, ignore_index=True)
            periodos['DNI'] = result['DNI']  # Asegurarnos de agregar el DNI a periodos
            resultsPeriodos = pd.concat([resultsPeriodos, periodos], axis=0, ignore_index=True)
        except Exception as e:
            errores = pd.concat(
                [errores, pd.DataFrame([[file.name, str(e)]], columns=['Archivo', 'Error'])],
                ignore_index=True
            )
            continue
    progress_bar.empty()
    res, cal, tab, err, eval_periodos = st.tabs(['Resultados', 'Cálculos', 'Tablas', 'Errores', 'Evaluaciones por Periodo'])
    if not results.empty:
        results = results.set_index('DNI')
        resultsData['NOTA'] = resultsData['NOTA'].map(lambda x: float(x) if str(x).isdigit() else x)
        dni = res.selectbox("Filtrar por DNI:", options=results.index, index=0)
        with res:
            st.dataframe(results.drop(columns='MinADyA'), use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer:
                results.to_excel(writer)
            st.download_button("Descargar", data=buffer, file_name="Resultado_UPCH.xlsx", mime="application/vnd.ms-excel")
            aplica = results.loc[dni, 'Excepcion'] == 'Sí'
            st.subheader("Resultado de Aplicación")
            if aplica:
                st.success("El estudiante es válido para la modalidad FACTOR EXCELENCIA👏")
            else:
                st.error("El postulante no es válido para la modalidad Factor Excelencia, lo invitamos a que postule a otras modalidades de admisión 😧")
        with cal:
            st.dataframe(resultsCount.query(f'DNI == "{dni}"').drop(columns='DNI').set_index('NOTA').T)
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
        with eval_periodos:
            st.dataframe(resultsPeriodos.query(f'DNI == "{dni}"'), use_container_width=True)
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


