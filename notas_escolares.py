import io
import tempfile
import pandas as pd
import streamlit as st
import time
from notas import procesar_pdf,cumple_excepcion,calcular_promedios,escolar_o_egresado,cumple_its

# creamos un directorio temporal
TEMP = tempfile.TemporaryDirectory()

# TODO: Obtener la lista de colegios de una base de datos
@st.cache_resource(show_spinner=False)
def get_colegios_ITS():
    return pd.read_excel(
        # Agregar aca el listado de colegios ITS
        'Listado de colegios ITS 2024.xlsx',
        dtype=str
    ).set_index('CODIGO MODULAR (MINEDU)')

@st.cache_data(persist="disk",show_spinner="Procesando ⏳")
def procesar(file,minADA):
    # Se usa está función para tener cache y no se recalcule
    global TEMP
    dni,nombre,documento,df = procesar_pdf(file,pwd=TEMP.name)
    tipo = escolar_o_egresado(df)
    prom1a4,prom1a5,notaR = calcular_promedios(df)
    its,colegios = cumple_its(df,get_colegios_ITS())
    cumple,counts = cumple_excepcion(df,minADA)
    result = pd.Series({
        'DNI':dni,
        'Nombre': nombre,
        'Excepcion':cumple,
        'Prom1a4':prom1a4,
        'Prom1a5':prom1a5,
        'Tipo': tipo,
        'Cumple ITS': its,
        'Documento':documento,
        'MinADyA':minADA,
    })
    notas = counts.drop(columns='DNI').set_index('NOTA')['Cantidad'].rename(0)
    result = pd.concat([result,notas],axis=0)
    result = result.reindex(['DNI','Nombre','Tipo','Cumple ITS','Excepcion','Prom1a4','Prom1a5','AD','A','B','C','Documento','MinADyA'])
    return result,df,counts,notaR,colegios

def main():
    st.set_page_config(initial_sidebar_state='collapsed')
    st.title('Notas escolares')
    with st.sidebar:
        minADA = 72
        min = st.select_slider(
            'Cantidad mínima de AD y A para aprobar:',
            options=range(1,89),
            value=72,
            help='Cambiar el valor reprocesará todos los archivos actualmente cargados, se recomienda hacerlo antes de la carga de archivos'
        )
        btn = st.button("Aplicar")
        if btn:
            minADA = min
    files = st.file_uploader('Archivo PDF COE o CLA:',accept_multiple_files=True)
    if not files:
        return
    progress_bar = st.progress(0, text="Procesando archivos...")
    results = pd.DataFrame() # resultados finales
    resultsData = pd.DataFrame() # Tidy data
    resultsCount = pd.DataFrame() # Cantidad de notas
    resultsR = pd.DataFrame() # Promedios por areas
    resultsColegios = pd.DataFrame() # Colegios por grados
    errores = pd.DataFrame()
    n = len(files)
    for i,file in enumerate(files):
        progress_bar.progress((i+1)/n,f"Procesando archivo {i+1}...")
        try:
            result,data,count,notaR,colegios = procesar(file,minADA)
            results = pd.concat([results,result.to_frame().T],axis=0,ignore_index=True)
            resultsData = pd.concat([resultsData,data],axis=0,ignore_index=True)
            resultsCount = pd.concat([resultsCount,count],axis=0,ignore_index=True)
            resultsR = pd.concat([resultsR,notaR],axis=0,ignore_index=True)
            resultsColegios = pd.concat([resultsColegios,colegios],axis=0,ignore_index=True)
        except Exception as e:
            errores = pd.concat(
                [errores,pd.DataFrame([[file.name,str(e)]],columns=['Archivo','Error'])],
                ignore_index=True
            )
            continue
    progress_bar.empty()
    res,cal,tab,err = st.tabs(['Resultados','Cálculos','Tablas','Errores'])
    if not results.empty :
        results = results.set_index('DNI')
        #results = results.reindex(['Nombre','Tipo','Excepcion','Promedio','AD','A','B','C','Documento'],axis=1)
        resultsData['NOTA'] = resultsData['NOTA'].map(lambda x: float(x) if str(x).isdigit() else x)
        dni = progress_bar.selectbox("Filtrar DNI:", options = results.index, index=0)
        with res:
            st.dataframe(results.drop(columns='MinADyA'),use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer) as writer:
                results.to_excel(writer)
            st.download_button("Descargar",data=buffer,file_name="Resultado.xlsx",mime="application/vnd.ms-excel")
        with cal:
            st.dataframe(resultsColegios.query(f'DNI == "{dni}"').drop(columns='DNI').set_index('GRADO'))
            st.dataframe(resultsCount.query(f'DNI == "{dni}"').drop(columns='DNI').set_index('NOTA').T)
            prom = resultsR.query(f'DNI == "{dni}"').pivot(index=['DESC'],columns='GRADO',values='NOTA')
            st.dataframe(pd.concat([
                prom,
                prom.mean().rename('**PROMEDIO**').to_frame().T,
                prom.count().rename('**CANTIDAD**').to_frame().T
            ]).round(2),use_container_width=True)
        with tab:
            d = resultsData.query(f'DNI == "{dni}"').drop(columns='DNI')
            st.dataframe(
                d[d['COMP'].isnull()].pivot(
                    index=['DESC'],columns='GRADO',values='NOTA'
                ),
                use_container_width=True
            )
            st.dataframe(
                d[d['COMP'].notnull()].pivot(
                    index=['DESC','COMP'],columns='GRADO',values='NOTA'
                ),
                use_container_width=True
            )
    if errores.empty:
        with err:
            st.write("No se encontraron errores")
    else:
        with err:
            st.dataframe(errores,use_container_width=True)
        with res:
            st.error(f'Hay {errores.shape[0]} archivo(s) con error!')
        
if __name__ == '__main__':
    main()