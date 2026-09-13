FROM mcr.microsoft.com/playwright/python:v1.50.1-noble
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system .
COPY app app
COPY alembic alembic
COPY alembic.ini .
RUN useradd --create-home --uid 10001 crawlforge
USER crawlforge
CMD ["celery", "-A", "app.workers.celery_app.celery", "worker", "--loglevel=INFO", "--concurrency=2"]
