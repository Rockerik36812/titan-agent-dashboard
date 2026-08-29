FROM python:3.13-slim

WORKDIR /app

# Install ca-certificates for HTTPS requests
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY main.py .
COPY static/ ./static/

EXPOSE 8999

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8999"]