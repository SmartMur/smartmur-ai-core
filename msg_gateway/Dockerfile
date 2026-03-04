FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml .
COPY superpowers/ superpowers/
COPY msg_gateway/ msg_gateway/

RUN pip install --no-cache-dir . slack_sdk

EXPOSE 8100

CMD ["uvicorn", "msg_gateway.app:app", "--host", "0.0.0.0", "--port", "8100"]
