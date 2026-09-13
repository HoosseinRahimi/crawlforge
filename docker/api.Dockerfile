FROM python:3.12-slim
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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
