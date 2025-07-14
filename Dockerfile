# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create entrypoint script to handle Docker socket permissions
RUN echo '#!/bin/bash\n\
# Fix Docker socket permissions if mounted\n\
if [ -S /var/run/docker.sock ]; then\n\
    echo "Docker socket found, adjusting permissions..."\n\
    chmod 666 /var/run/docker.sock 2>/dev/null || echo "Could not adjust Docker socket permissions (this is normal in some environments)"\n\
fi\n\
\n\
# Start the application\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "--timeout", "60", "app:app"]
