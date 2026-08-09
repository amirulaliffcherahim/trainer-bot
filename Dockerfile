# python:3.11-slim — small runtime; torch/easyocr install from CPU index
# to keep the image lean (the default PyPI torch wheel is the CUDA build).
FROM python:3.11-slim

# Runtime libraries required by OpenCV / EasyOCR on headless Linux
# (also needed on a bare pm2 host: apt install libgl1 libglib2.0-0)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user FIRST (before any COPY of application code).
RUN useradd --create-home --uid 1000 trainer \
    && mkdir -p /app/data /app/logs \
    && chown -R trainer:trainer /app

USER trainer
WORKDIR /app

COPY --chown=trainer:trainer requirements.txt .
RUN pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=trainer:trainer . .

ENV DB_PATH=/app/data/trainer_data.db \
    LOG_LEVEL=INFO

# Long-polling: no webhook, no exposed port needed.
CMD ["python", "bot.py"]
