FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Install minimal build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files for caching
COPY pyproject.toml uv.lock ./

# Install uv (fast dependency resolver)
RUN pip install --no-cache-dir uv

# Create isolated environment
RUN uv venv --python python

FROM base AS deps

WORKDIR /app

# Force CPU-only torch installation to avoid NVIDIA libs
RUN uv pip install --extra-index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio

# Install the rest of your dependencies (will reuse torch above)
RUN uv pip install --no-cache-dir .

FROM python:3.12-slim

WORKDIR /app

# Copy from deps layer
COPY --from=deps /usr/local /usr/local
COPY --from=deps /app /app

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/usr/local/bin:$PATH"

EXPOSE 8000

# Run your FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
