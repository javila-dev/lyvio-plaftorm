FROM python:3.11-slim

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    # PostgreSQL
    libpq-dev \
    postgresql-client \
    # Compilación
    build-essential \
    gcc \
    g++ \
    # Utilidades
    curl \
    wget \
    git \
    # Para Pillow (imágenes)
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff-dev \
    libwebp-dev \
    # Para procesamiento de PDFs
    poppler-utils \
    # Limpieza
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 lyvio && \
    mkdir -p /app && \
    chown -R lyvio:lyvio /app

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements como root primero
COPY --chown=lyvio:lyvio requirements.txt /app/

# Actualizar pip
RUN pip install --upgrade pip setuptools wheel

# Instalar dependencias Python
RUN pip install -r requirements.txt

# Cambiar a usuario no-root
#USER lyvio

# Copiar el código de la aplicación
COPY --chown=lyvio:lyvio . /app/

# Crear directorios necesarios con permisos correctos
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Exponer puerto
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Comando por defecto (se sobreescribe en docker-compose)
CMD ["gunicorn", "lyvio.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]