FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create directory for wait-for-db script
RUN mkdir -p /app/omnichannel_core/management/commands/

# Add wait-for-db command
COPY docker/backend/wait_for_db.py /app/omnichannel_core/management/commands/wait_for_db.py

# Copy project
COPY . .

# Create media and static directories
RUN mkdir -p /app/media /app/staticfiles /app/logs

# Run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Command will be provided in docker-compose.yml
