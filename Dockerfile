FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY main.py .
COPY sw.js .
COPY static/ ./static/

EXPOSE 8999

# Healthcheck con python a propósito: python:3.13-slim no trae curl ni wget.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8999/health', timeout=4).status == 200 else 1)"

# Sigue corriendo como root A PROPÓSITO: necesita el docker.sock y monta rutas
# del host; con otro usuario habría que igualar el gid del socket y los uids de
# /app/data (cambiarlo sin probar deja el panel sin Docker y sin volumen).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8999"]