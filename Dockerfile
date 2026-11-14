FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1001 appuser
WORKDIR /app
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/base.txt
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir --no-deps -e .

FROM base AS api
COPY alembic/ alembic/
COPY alembic.ini ./
RUN install -d -o appuser -g appuser /data
USER appuser
CMD ["uvicorn", "devflow_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS ui
USER appuser
CMD ["streamlit", "run", "src/devflow_ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
