
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system build deps (only for build stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for caching
COPY pyproject.toml uv.lock ./

# Install uv and sync dependencies into isolated venv
RUN pip install --no-cache-dir uv \
    && uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && uv sync --frozen

# Copy only the application source (after deps)
COPY . .

FROM python:3.12-slim

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy app source code
COPY --from=builder /app /app

# Expose FastAPI port
EXPOSE 8000

# Healthcheck (optional but recommended)
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Start app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
