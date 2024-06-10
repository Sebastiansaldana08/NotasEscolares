import os
import io
import tempfile
import pandas as pd
import streamlit as st
import base64
from notas import procesar_pdf, escolar_o_egresado, calcular_promedios, cumple_excepcion, evaluar_periodos, procesar
from streamlit_option_menu import option_menu

# Especificar la ruta de Ghostscript
if os.name == 'nt':  # Si es Windows
    os.environ["PATH"] += os.pathsep + r'C:\Program Files\gs\gs10.03.1\bin'
else:  # Si es otro sistema operativo (por ejemplo, Linux)
    os.environ["PATH"] += os.pathsep + r'/usr/bin'

# Crear un directorio temporal
TEMP = tempfile.TemporaryDirectory()

@st.cache_data(persist="disk", show_spinner="Procesando ⏳")
def procesar_archivo(file, minADA, carrera):
    global TEMP
    dni, nombre, documento, df, grado_maximo = procesar_pdf(file, pwd=TEMP.name)
    #print(f"Grado máximo en procesar_archivo: {grado_maximo}")  # Imprimir grado máximo para depuración
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
        <div style="text-align: justify; font-size: 1.2em;">
            <h2 style="font-size: 1.4em;"><strong>Modalidad FACTOR EXCELENCIA</strong></h2>
            <p>Este aplicativo determina si los postulantes son aptos para postular por la modalidad de admisión FACTOR EXCELENCIA.</p>
            <p><strong>Para utilizar el aplicativo, deberás seguir los siguientes pasos:</strong></p>
            <ol>
                <li>Seleccionar la carrera a la cual está postulando el interesado: Medicina u otras Carreras UPCH.</li>
                <li>Subir el Certificado Oficial de Estudios o la Constancia de Logros de Aprendizaje (CLA) en formato PDF en donde dice “Carga tu Certificado de Estudios”.</li>
                <li>Leer el resultado para determinar si cumple con el requisito de Factor Excelencia.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
    
    # Agregar los desplegables
    with st.expander("Requisitos para postular por Factor Excelencia de acuerdo con el Reglamento de Admisión Vigente. (Certificado con notas numéricas)"):
        st.markdown("""
        <ul>
            <li>Los estudiantes del 5° año de secundaria y egresados de estudios secundarios en el país o extranjero (máximo hasta con dos (02) años del egreso).</li>
            <li>Haber obtenido un promedio de 14 o más o se encuentren en el tercio superior del colegio de procedencia (para todas las carreras profesionales excepto Medicina Humana). El promedio o cálculo del tercio superior se puede realizar usando los siguientes años académicos:
                <ul>
                    <li>Del 1° al 4° de secundaria.</li>
                    <li>De 1° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.</li>
                    <li>De 3° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.</li>
                </ul>
            </li>
            <li>Los que postulan a la carrera de Medicina, haber obtenido un promedio de 16 o más o acreditar haber estado en el tercio superior en 3°, 4° y 5° (si se encuentra estudiando el 5° año presentar la libreta de notas incluyendo el último bimestre cursado).</li>
        </ul>
        """, unsafe_allow_html=True)

    with st.expander("Requisitos para postular por Factor Excelencia de acuerdo con el Reglamento de Admisión Vigente. (Certificado con notas literales)"):
        st.markdown("""
        <ul>
            <li>Los postulantes que se presentan a la modalidad de Factor Excelencia y envíen su certificado de estudio o constancia de logros de aprendizaje con notas literales, deben de tener como mínimo el 90% con calificación A o AD en las siguientes áreas curriculares y competencias: ARTE Y CULTURA, CIENCIA Y TECNOLOGÍA, CIENCIAS SOCIALES, COMUNICACIÓN, DESARROLLO PERSONAL, CIUDADANÍA Y CÍVICA, EDUCACIÓN PARA EL TRABAJO Y MATEMÁTICA.</li>
            </li>
            <li>El cálculo del porcentaje mínimo se puede realizar usando los siguientes años académicos:
                <ul>
                    <li>Todas las carreras excepto medicina:
                        <ul>
                            <li>Promedio del 1° al 4° de secundaria.</li>
                            <li>Promedio del 1° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.</li>
                            <li>Promedio del 3° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.</li>
                        </ul>
                    </li>
                    <li>Medicina:
                        <ul>
                            <li>Promedio del 1° al 4° de secundaria.</li>
                            <li>Promedio del 1° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.</li>
                            <li>Promedio del 3° año a los bimestres de 5° de Secundaria cursados hasta la fecha de postulación con libreta de notas.</li>
                        </ul>
                    </li>
                </ul>
            </li>
        </ul>
        """, unsafe_allow_html=True)
    
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
    # Selección de carrera utilizando streamlit_option_menu
    carrera = option_menu(
        menu_title="Selecciona la carrera",
        options=["MEDICINA", "Todas las carreras, excepto MEDICINA"],
        icons=["activity", "book"],
        menu_icon="cast",
        default_index=0,
        orientation="vertical"
    )
    
    # Carga de archivos
    files = st.file_uploader('Adjunta tu Certificado de Estudios COE o CLA', accept_multiple_files=True, type=['pdf'])
    if not files:
        return
    progress_bar = st.progress(0, text="Procesando archivos...")
    results = pd.DataFrame()  # resultados finales
    resultsData = pd.DataFrame()  # Tidy data
    resultsCount = pd.DataFrame()  # Cantidad de notas
    resultsR = pd.DataFrame()  # Promedios por áreas
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
        with res:
            dni_options = results.index.unique().tolist()
            dni = st.selectbox("Filtrar DNI:", options=dni_options, index=dni_options.index(last_dni) if last_dni in dni_options else 0)
            st.write("Resultados por Periodo:")
            periodos_filtrados = resultsColegios[resultsColegios['DNI'] == dni]
            if not periodos_filtrados.empty:
                st.dataframe(periodos_filtrados.drop(columns='DNI').reset_index(drop=True))
                
                # Verificar si el estudiante aplica o no
                aplica = (periodos_filtrados['ESTADO'] == 'CUMPLE').any()
                if aplica:
                    st.success("El estudiante APLICA para esta modalidad de admisión.👏")
                else:
                    st.error("El estudiante NO APLICA para esta modalidad de admisión.")
            else:
                st.write("No hay resultados para mostrar.")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer:
                results.to_excel(writer)
            st.download_button("Descargar", data=buffer, file_name="Resultado.xlsx", mime="application/vnd.ms-excel")
        with cal:
            if 'GRADO' in resultsColegios.columns:
                st.dataframe(resultsColegios.query(f'DNI == "{dni}"').drop(columns='DNI').set_index('GRADO'))
            if 'NOTA' in resultsCount.columns:
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

