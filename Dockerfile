FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first for caching
COPY pyproject.toml uv.lock ./

# Create isolated environment in /install and install deps deterministically
RUN pip install --no-cache-dir uv \
    && uv venv --python python3 /install \
    && . /install/bin/activate \
    && uv sync

# Copy the app source
COPY . .

FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy app source code
COPY --from=builder /app /app

# Expose FastAPI port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
