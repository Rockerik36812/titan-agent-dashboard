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

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8999"]