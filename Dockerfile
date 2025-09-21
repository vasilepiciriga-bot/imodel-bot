FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

COPY . .

# FastAPI на 8080 (Railway экспонирует сам)
CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8080"]
