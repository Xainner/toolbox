FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    U2NET_HOME=/srv/models

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 libjpeg62-turbo zlib1g fonts-dejavu-core libgomp1 \
    ghostscript tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /tmp/u2net

COPY app ./app
COPY tools ./tools

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS cpu

FROM runtime AS gpu
RUN pip uninstall -y onnxruntime && pip install --no-cache-dir onnxruntime-gpu==1.22.0
