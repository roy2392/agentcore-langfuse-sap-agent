# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements-ui.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements-ui.txt

# Copy application files
COPY app.py .
COPY utils/ ./utils/
COPY agents/ ./agents/
COPY cicd/ ./cicd/
COPY templates/ ./templates/
COPY static/ ./static/

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Use gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 120 app:app
