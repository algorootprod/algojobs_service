# Use Python slim as base
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . .

RUN uv venv && \
    . .venv/bin/activate && \
    uv sync  # installs dependencies from pyproject.toml and uv.lock

# Expose FastAPI port
EXPOSE 8000

# Run the app using UV environment
CMD ["/bin/bash", "-c", ". .venv/bin/activate && uv run python main.py"]
