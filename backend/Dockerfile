FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && python -m spacy download en_core_web_sm \
    && python -m spacy validate \
    && addgroup --system veritygraph \
    && adduser --system --ingroup veritygraph --home /home/veritygraph veritygraph \
    && mkdir -p /data /backups \
    && chown -R veritygraph:veritygraph /data /backups /home/veritygraph

USER veritygraph

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
