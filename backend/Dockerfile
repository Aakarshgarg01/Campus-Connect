# Production image for the FastAPI backend.
# Python 3.13 matches the environment the committed models were trained in (see
# models_store/*/metadata.json -> library_versions); requirements.txt pins the same
# scikit-learn/SHAP versions, and the model loader refuses a scikit-learn mismatch.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# CA bundle for verifying managed MySQL TLS certificates (DB_SSL_CA=/etc/ssl/certs/ca-certificates.crt).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini docker-entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app
COPY models_store ./models_store

RUN chmod +x docker-entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
