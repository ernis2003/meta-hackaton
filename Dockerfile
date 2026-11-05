# syntax=docker/dockerfile:1

# Backend includes native Zeek: no Docker socket or privileged container required.
FROM zeek/zeek@sha256:524cb0ce29f26a6a954fb9c357a8f92b95812476d8240f0ece26617ace249dd0 AS backend
USER root
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:${PATH}"
RUN apt-get update \
    && apt-get install --no-install-recommends -y python3-venv ca-certificates \
    && python3 -m venv /opt/venv \
    && rm -rf /var/lib/apt/lists/*
ARG JA4_REVISION=8bf9feca52790ae8c926c6a8d79a3547ac19541a
COPY backend/zeek/install_ja4.py /tmp/install_ja4.py
RUN JA4_REVISION=${JA4_REVISION} python /tmp/install_ja4.py
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/main.py backend/manage.py ./
COPY backend/src ./src
COPY actions/install_ja4_sample.py /app/actions/install_ja4_sample.py
COPY docker/backend_entrypoint.py /app/docker/backend_entrypoint.py
RUN python /app/actions/install_ja4_sample.py \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /app /data
ENV DATABASE_PATH=/data/app.sqlite3 ZEEK_MODE=native ZEEK_BIN=/usr/local/zeek/bin/zeek ZEEK_SCRIPTS=ja4
USER app
EXPOSE 8001
ENTRYPOINT ["python", "/app/docker/backend_entrypoint.py"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_SAME_ORIGIN=true
RUN npm run build

FROM nginx:stable-alpine AS frontend
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]

# Optional GPU inference; no training dependencies or private weights in the image.
FROM python:3.12-slim AS inference
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/cache/huggingface
WORKDIR /app/backend
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements-inference.txt ./
RUN pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cu128 \
    && pip install --no-cache-dir -r requirements-inference.txt
COPY backend/src/ai/__init__.py backend/src/ai/common.py ./src/ai/
COPY backend/src/ai/llm ./src/ai/llm
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /cache/huggingface \
    && chown -R app:app /app /cache
USER app
EXPOSE 8002
CMD ["uvicorn", "src.ai.llm.server:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
