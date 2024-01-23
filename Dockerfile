FROM python:3.11-slim-bookworm

WORKDIR /usr/src/app

# Enable contrib repo
RUN sed -i'.bak' '/^Components:/s/$/ contrib/' /etc/apt/sources.list.d/debian.sources

RUN apt-get -y update && apt-get install -y dumb-init ghostscript python3-tk ffmpeg libsm6 libxext6 --no-install-recommends

COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD [ "streamlit","run", "./notas_escolares.py" ]