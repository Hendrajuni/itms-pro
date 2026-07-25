# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN sed -i "s|http://|https://|g" /etc/apt/sources.list.d/debian.sources || true && \
    sed -i "s|http://|https://|g" /etc/apt/sources.list || true && \
    apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install gunicorn psycopg2-binary

# Copy project
COPY . /app/

# Create directory for static root if not exists (though collectstatic will do it)
RUN mkdir -p /app/staticfiles /app/media

# Expose port
EXPOSE 8000

# Default command (will be overridden by compose or entrypoint)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
