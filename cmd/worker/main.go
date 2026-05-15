package main

import (
    "context"
    "log"
    "os"

    "github.com/hibiken/asynq"
    "imodel-bot/internal/config"
    "imodel-bot/internal/log"
    "imodel-bot/internal/repo"
    "imodel-bot/internal/services/queue"
)

func main() {
    cfg := config.Load()
    logger := ilog.New(cfg.Env)
    ctx := context.Background()

    store, _ := repo.New(ctx, cfg.PostgresURL)
    defer store.Close()

    srv := asynq.NewServer(asynq.RedisClientOpt{Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: cfg.RedisDB}, asynq.Config{
        Concurrency: cfg.WorkerConcurrency,
        Queues:      map[string]int{queue.QueuePro: 30, queue.QueueCritical: 20, queue.QueueDefault: 10},
    })
    h := queue.NewHandler(cfg, logger, store)
	mux := asynq.NewServeMux()
	mux.Handle(queue.TypeGenerate, asynq.HandlerFunc(h.HandleGenerate))
	mux.Handle(queue.TypeUpscale, asynq.HandlerFunc(h.HandleUpscale))
	mux.Handle(queue.TypePublish, asynq.HandlerFunc(h.HandlePublish))
	mux.Handle(queue.TypeNudge, asynq.HandlerFunc(h.HandleNudge))

	log.Println("worker starting...")
	if err := srv.Run(mux); err != nil {
		log.Println("worker stopped:", err)
		os.Exit(1)
	}
	_ = ctx
}
