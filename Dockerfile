FROM python:3.12-slim

WORKDIR /app
COPY requirements-minimal.txt .

RUN apt-get update && apt-get install -y build-essential git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
# install using CPU wheel index for torch if needed
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-minimal.txt

COPY . .
CMD ["python", "main.py"]