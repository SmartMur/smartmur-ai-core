FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl iputils-ping dnsutils procps net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY superpowers/ superpowers/
COPY dashboard/ dashboard/

RUN pip install --no-cache-dir .

EXPOSE 8200

CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8200"]
