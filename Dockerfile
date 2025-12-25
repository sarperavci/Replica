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
COPY replica/ ./replica/
COPY .env.example .env

# Ensure the app package is importable
ENV PYTHONPATH=/app

EXPOSE 8000

# Entry point performs validations and starts the server
# Run as module to support relative imports
ENTRYPOINT ["python", "-m", "replica.entrypoint"]
