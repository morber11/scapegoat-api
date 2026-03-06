FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    REQUEST_TIMEOUT_SECONDS=30 \
    RATE_LIMIT_REQUESTS=5 \
    RATE_LIMIT_WINDOW_SECONDS=60

WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY pyproject.toml pyproject.toml
RUN pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir .

COPY src/ src/

WORKDIR /app/src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
