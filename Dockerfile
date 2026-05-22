FROM node:20-slim AS webapp_build
WORKDIR /webapp
COPY webapp/package.json webapp/package-lock.json* ./
RUN npm install
COPY webapp/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

COPY . .
COPY --from=webapp_build /webapp/dist /app/webapp/dist

# FastAPI на 8080 (Railway экспонирует сам)
CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8080"]
