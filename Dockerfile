FROM python:3.10-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# install build/runtime deps needed for some packages on Alpine
RUN apk add --no-cache --virtual .build-deps build-base libffi-dev openssl-dev \
    && apk add --no-cache ca-certificates

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

# copy package source
COPY src/ ./src/
COPY .env.example .env

ENV PYTHONPATH=/app/src

EXPOSE 8000

# Entry point performs validations and starts the server
ENTRYPOINT ["python", "/app/src/replica/entrypoint.py"]
