# Use Python 3.12 slim image as base
FROM python:3.15.0a8-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    IS_RUNNING_IN_CONTAINER=true

# Install system dependencies for lxml and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for token cache
RUN mkdir -p /app/cache

# Expose port for OAuth redirect (if needed)
EXPOSE 9090

# Set the default command (running as root to avoid permission issues with mounted volumes)
CMD ["python", "main.py"]