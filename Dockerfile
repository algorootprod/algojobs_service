FROM python:3.13-slim AS builder

WORKDIR /app

# Install minimal build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for caching
COPY pyproject.toml uv.lock ./

# Install uv and create deterministic venv
RUN pip install --no-cache-dir uv \
    && uv venv --python python3 /install \
    && . /install/bin/activate \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && uv sync

# Copy app source
COPY . .

# Production stage
FROM python:3.13-slim

WORKDIR /app

# Copy venv from builder
COPY --from=builder /install /usr/local

# Copy app source
COPY --from=builder /app /app

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
