FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps required for psycopg2, node, and common wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev build-essential nodejs npm \
    && npm install -g @google/gemini-cli \
    && rm -rf /var/lib/apt/lists/* /root/.npm

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./requirements.txt

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt \
    && pip cache purge || true

# Copy application source
COPY . /app

EXPOSE 8000

# Default command (can be overridden by compose command)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
