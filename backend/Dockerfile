FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Entrypoint: corre las migraciones Alembic antes de arrancar la API.
# Se copia FUERA de /app a /usr/local/bin porque docker-compose monta el código
# host con un volumen (./backend:/app) que taparia el archivo en runtime; en
# /usr/local/bin sobrevive al montaje. El `sed` normaliza CRLF->LF por si el
# archivo se editó en Windows (un \r en el shebang rompe el script en Linux).
RUN cp /app/entrypoint.sh /usr/local/bin/recruitai-entrypoint.sh \
    && sed -i 's/\r$//' /usr/local/bin/recruitai-entrypoint.sh \
    && chmod +x /usr/local/bin/recruitai-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/recruitai-entrypoint.sh"]
