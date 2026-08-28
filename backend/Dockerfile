FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SKIP_SYSTEM_DEPS=1 \
    ENABLE_LEGACY_AI_ROUTES=0 \
    ENABLE_PUBLIC_TUTOR=1 \
    OPENAI_TUTOR_MODEL=gpt-5.6-luna

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements-production.txt .
RUN pip install --no-cache-dir -r requirements-production.txt

COPY backend/ .
COPY frontend/src/components/games/ /app/game_templates/
COPY marketing/ /app/marketing/

RUN mkdir -p \
        /app/backend/storage/projects \
        /app/backend/storage/audio \
        /app/backend/storage/exports \
        /app/backend/storage/uploads \
        /app/backend/storage/assets \
        /app/backend/storage/scorm_preview

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
