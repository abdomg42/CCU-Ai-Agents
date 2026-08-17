# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthchecks, gcc for sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=1000 --retries=3 -r requirements.txt

# Copy the application
COPY . .

RUN chmod +x scripts/seed_graph.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
