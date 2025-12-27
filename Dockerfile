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

# Run the application directly using uvicorn.
# Validation and diagnostics are performed on startup via FastAPI lifespan.
CMD ["uvicorn", "replica.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
