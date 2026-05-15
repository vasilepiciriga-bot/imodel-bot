.PHONY: web worker build run-web run-worker migrate set-webhook compose-up compose-build env-migrate

build:
	CGO_ENABLED=0 go build -o bin/web ./cmd/web
	CGO_ENABLED=0 go build -o bin/worker ./cmd/worker

run-web:
	go run ./cmd/web

run-worker:
	go run ./cmd/worker

migrate:
	go run ./scripts/migrate.go

set-webhook:
	go run ./scripts/set_webhook.go -token $$BOT_TOKEN -url $$PUBLIC_URL/tg/webhook -secret $$WEBHOOK_SECRET

compose-build:
	docker compose build

compose-up:
	docker compose up -d

env-migrate:
	go run ./scripts/env_migrate.go -in old.env -out .env
