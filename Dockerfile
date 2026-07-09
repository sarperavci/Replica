FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy package source
COPY replica/ ./replica/

ENV PYTHONPATH=/app

EXPOSE 8000

# Validation and diagnostics run on startup via FastAPI lifespan.
CMD ["uvicorn", "replica.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
