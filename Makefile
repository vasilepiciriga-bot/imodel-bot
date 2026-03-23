.PHONY: web worker build run-web run-worker migrate

build:
	CGO_ENABLED=0 go build -o bin/web ./cmd/web
	CGO_ENABLED=0 go build -o bin/worker ./cmd/worker

run-web:
	go run ./cmd/web

run-worker:
	go run ./cmd/worker

migrate:
	@echo "Run goose or golang-migrate with migrations/ on $(DATABASE_URL)"
