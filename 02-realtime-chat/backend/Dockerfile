FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir uv && \
    uv sync

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
