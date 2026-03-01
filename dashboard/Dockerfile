FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY superpowers/ superpowers/
COPY dashboard/ dashboard/

RUN pip install --no-cache-dir .

EXPOSE 8200

CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8200"]
