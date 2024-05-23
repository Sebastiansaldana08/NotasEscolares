<<<<<<< HEAD
# NotasEscolares
App para calcular el puntaje de notas escolares a partir del certificado en PDF

## Instalación

### Opción 1

1. Instalar dependencias `ghostscript` y `python3-tk` [(ver más detalle)](https://camelot-py.readthedocs.io/en/master/user/install-deps.html)
2. Crear entorno virtual `python -m venv venv`
3. Activar entorno virtual `source ./venv/bin/activate`
4. Instalar librerías `pip install -r requirements.txt`
5. Iniciar aplicación `streamlit run notas_escolares.py`
6. Ingresar al enlace Local que carga en la terminal

### Opción 2 - Docker

1. Construir la imagen `docker build . -t notas_escolares`
2. Correr la aplicación `docker run -v .:/usr/src/app --rm notas_escolares`
3. Ingresar al enlace Local que carga en la terminal
=======
# NotasEscolares
>>>>>>> 0b4c7cf9a7dc94b4576423c67b10d4b9f88daf4f
