FROM python:3.12-slim AS builder

WORKDIR /app

# Install system build deps (for building wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files for caching
COPY pyproject.toml uv.lock ./

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Create venv and install ONLY CPU dependencies
RUN uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    # install CPU-only PyTorch wheel explicitly (no CUDA)
    && pip install --no-cache-dir torch==2.5.1+cpu torchvision==0.20.1+cpu torchaudio==2.5.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    # sync other dependencies
    && uv sync --frozen

# Copy all source files (includes main.py and app/)
COPY . .


FROM python:3.12-slim

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UVICORN_WORKERS=1 \
    OMP_NUM_THREADS=1 \
    TORCH_CUDA_AVAILABLE=0

# Copy the app source
COPY --from=builder /app /app

# Expose FastAPI port
EXPOSE 8000

# Healthcheck (optional)
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Start the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
