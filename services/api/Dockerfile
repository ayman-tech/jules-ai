FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice nodejs npm poppler-utils fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY services/api/pyproject.toml ./
RUN pip install --no-cache-dir .
COPY services/artifact-renderer ./artifact-renderer
RUN npm install --omit=dev --prefix ./artifact-renderer
COPY services/api/app ./app
COPY services/api/alembic.ini ./alembic.ini
COPY services/api/alembic ./alembic
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
