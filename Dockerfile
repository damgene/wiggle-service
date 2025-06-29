FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy wiggle-common first
COPY ../wiggle-common /tmp/wiggle-common
RUN pip install /tmp/wiggle-common

# Copy application code
COPY . .

# Install requirements and the package
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e .

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "wiggle_service.main", "--host", "0.0.0.0", "--port", "8000"]