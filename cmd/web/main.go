package main

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "os"
    "strings"
    "time"

    "github.com/gofiber/fiber/v2"
    "github.com/hibiken/asynq"
    "imodel-bot/internal/bot"
    "imodel-bot/internal/config"
    "imodel-bot/internal/log"
    "imodel-bot/internal/repo"
    "imodel-bot/internal/services/queue"
)

func main() {
    cfg := config.Load()
    logger := ilog.New(cfg.Env)
    ctx := context.Background()

    // Postgres store (optional)
    store, _ := repo.New(ctx, cfg.PostgresURL)
    defer store.Close()

    // Asynq client
    asynqClient := asynq.NewClient(asynq.RedisClientOpt{Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: cfg.RedisDB})
    defer asynqClient.Close()

    // Init Telebot (handlers register here). We don't Start() since Fiber handles HTTP.
    if err := bot.InitTele(ctx, cfg, logger, asynqClient, store); err != nil {
        log.Println("telebot init warning:", err)
    }

    // HTTP server
    app := fiber.New(fiber.Config{DisableStartupMessage: true})

	// Health
	app.Get("/healthz", func(c *fiber.Ctx) error { return c.SendStatus(http.StatusOK) })

    // Metrics (Prometheus format)
    app.Get("/metrics", func(c *fiber.Ctx) error {
        ins := asynq.NewInspector(asynq.RedisClientOpt{Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: cfg.RedisDB})
        q := queue.SnapshotQueues(ctx, ins)
        // Optional DB counts
        users, gens := 0, 0
        if store != nil && store.DB != nil {
            users = store.CountTable(ctx, "users")
            gens = store.CountTable(ctx, "generations")
        }
        b := &strings.Builder{}
        fmt.Fprintln(b, "imodel_up 1")
        fmt.Fprintln(b, "imodel_build_info{version=\"v3\"} 1")
        for name, pending := range q.Queues { fmt.Fprintf(b, "asynq_queue_pending{queue=\"%s\"} %d\n", name, pending) }
        fmt.Fprintf(b, "imodel_db_users %d\n", users)
        fmt.Fprintf(b, "imodel_db_generations %d\n", gens)
        c.Type("text/plain; version=0.0.4").SendString(b.String())
        return nil
    })

    // Telegram webhook
    app.Post("/tg/webhook", func(c *fiber.Ctx) error {
        secret := c.Get("X-Telegram-Bot-Api-Secret-Token")
        if cfg.WebhookSecret != "" && secret != cfg.WebhookSecret {
            return c.SendStatus(http.StatusUnauthorized)
        }
        // Forward raw body to telebot processor; fallback to minimal router
        if err := bot.ProcessWebhook(c.Body()); err != nil {
            var raw map[string]any
            if err2 := c.BodyParser(&raw); err2 == nil {
                _ = bot.HandleUpdate(ctx, cfg, logger, asynqClient, raw)
            }
        }
        return c.SendStatus(http.StatusOK)
    })

	// Admin minimal endpoints
    app.Get("/admin/queues", func(c *fiber.Ctx) error {
        if c.Get("X-Admin-Secret") != cfg.AdminSecret || cfg.AdminSecret == "" {
            return c.SendStatus(http.StatusUnauthorized)
        }
        ins := asynq.NewInspector(asynq.RedisClientOpt{Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: cfg.RedisDB})
        q := queue.SnapshotQueues(ctx, ins)
        return c.JSON(q)
    })

    // DLQ list and requeue
    app.Get("/admin/dlq", func(c *fiber.Ctx) error {
        if c.Get("X-Admin-Secret") != cfg.AdminSecret || cfg.AdminSecret == "" {
            return c.SendStatus(http.StatusUnauthorized)
        }
        ins := asynq.NewInspector(asynq.RedisClientOpt{Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: cfg.RedisDB})
        out := queue.SnapshotDLQ(ctx, ins)
        return c.JSON(out)
    })

    app.Post("/admin/dlq/requeue", func(c *fiber.Ctx) error {
        if c.Get("X-Admin-Secret") != cfg.AdminSecret || cfg.AdminSecret == "" {
            return c.SendStatus(http.StatusUnauthorized)
        }
        type req struct{ Queue string `json:"queue"`; ID string `json:"id"` }
        var r req
        if err := c.BodyParser(&r); err != nil { return c.SendStatus(http.StatusBadRequest) }
        ins := asynq.NewInspector(asynq.RedisClientOpt{Addr: cfg.RedisAddr, Password: cfg.RedisPassword, DB: cfg.RedisDB})
        if err := queue.RequeueTask(ctx, ins, r.Queue, r.ID); err != nil { return c.Status(400).JSON(fiber.Map{"error": err.Error()}) }
        return c.SendStatus(http.StatusOK)
    })

    // Simple daily stats (last 30 days)
    app.Get("/admin/stats", func(c *fiber.Ctx) error {
        if c.Get("X-Admin-Secret") != cfg.AdminSecret || cfg.AdminSecret == "" {
            return c.SendStatus(http.StatusUnauthorized)
        }
        rows, err := store.ListStatsDaily(ctx, 30)
        if err != nil { return c.Status(500).JSON(fiber.Map{"error": err.Error()}) }
        return c.JSON(rows)
    })

	addr := ":8080"
	if p := os.Getenv("PORT"); p != "" { addr = ":" + p }
	srv := &http.Server{ Addr: addr, Handler: app, ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second }
	log.Println("web listening on", addr)
	if err := app.Listener(srv); err != nil { log.Fatal(err) }
}
