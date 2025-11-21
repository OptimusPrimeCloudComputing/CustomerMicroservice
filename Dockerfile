FROM python:3.12-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Optional: non-root user
RUN useradd -m appuser
USER appuser

# Cloud Run sets PORT=8080
# Use shell form to expand PORT env variable
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"
