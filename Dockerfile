FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --upgrade pip setuptools wheel build && \
    python -m build --wheel && \
    pip install --no-cache-dir --target=/app/deps dist/*.whl


FROM gcr.io/distroless/python3-debian12 AS runtime

WORKDIR /app

COPY --from=builder /app/deps /app/.venv/lib/python3.11/site-packages
COPY src/ src/

ENV PYTHONPATH=/app/.venv/lib/python3.11/site-packages:/app/src \
    PYTHONUNBUFFERED=1

USER nonroot

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

ENTRYPOINT ["python", "-m", "uvicorn", "genai_platform.api:app", "--host", "0.0.0.0", "--port", "8000"]
