package queue

import (
    "context"
    "encoding/json"
    "errors"
    "fmt"
    "time"

    "github.com/hibiken/asynq"
    "imodel-bot/internal/config"
    "imodel-bot/internal/log"
    "imodel-bot/internal/repo"
    "imodel-bot/internal/services/replicate"
    "imodel-bot/internal/services/storage"
    "imodel-bot/internal/services/images"
)

type Handler struct {
    cfg config.Config
    log ilog.Logger
    rep *replicate.Client
    s3  *storage.S3
    db  *repo.Store
}

func NewHandler(cfg config.Config, logger ilog.Logger, db *repo.Store) *Handler {
    return &Handler{cfg: cfg, log: logger, rep: replicate.New(cfg.ReplicateToken), s3: storage.New(cfg), db: db}
}

func (h *Handler) HandleGenerate(ctx context.Context, t *asynq.Task) error {
	var p GeneratePayload
	if err := json.Unmarshal(t.Payload(), &p); err != nil { return err }
	if h.rep == nil { return errors.New("replicate not configured") }

    // Insert generation row (queued)
    if h.db != nil {
        _ = h.db.InsertGeneration(ctx, p.GID, p.ChatID, p.Mode, "", p.Prompt, p.Negative, p.Seed, p.StyleURL, p.SelfieURL)
    }
    // Call replicate NanoBanana model
    url, err := h.rep.Generate(ctx, h.cfg.NanoBanana, map[string]any{
        "prompt": p.Prompt,
        "negative": p.Negative,
        "selfie_url": p.SelfieURL,
        "style_url": p.StyleURL,
        "seed": p.Seed,
    })
    if err != nil { return err }

    if h.cfg.PreviewFirst {
        // For MVP, reuse the same URL as preview
        if h.db != nil { _ = h.db.UpdateGenerationPreview(ctx, p.GID, url) }
    }

    // Enqueue upscale
    c := asynq.NewClient(asynq.RedisClientOpt{Addr: h.cfg.RedisAddr, Password: h.cfg.RedisPassword, DB: h.cfg.RedisDB})
    defer c.Close()
    _, err = EnqueueUpscale(ctx, c, UpscalePayload{GID: p.GID, ChatID: p.ChatID, URL: url})
    return err
}

func (h *Handler) HandleUpscale(ctx context.Context, t *asynq.Task) error {
	var p UpscalePayload
	if err := json.Unmarshal(t.Payload(), &p); err != nil { return err }
	if h.rep == nil { return errors.New("replicate not configured") }

    // ESRGAN upscale
    up, err := h.rep.Generate(ctx, h.cfg.ESRGAN, map[string]any{"image": p.URL, "scale": 4, "face_enhance": false})
    if err != nil || up == "" { up = p.URL }

    finalURL := up
    // Try save to S3 for durability
    if h.s3 != nil {
        if b, ct, err := images.Download(ctx, up, 25<<20); err == nil {
            key := fmt.Sprintf("generations/%d/%s/final.jpg", p.ChatID, p.GID)
            if err2 := h.s3.PutBytes(ctx, key, b, ct); err2 == nil {
                if u, err3 := h.s3.PresignGetURL(ctx, key, 30*24*time.Hour); err3 == nil { finalURL = u }
            }
        }
    }
    // Send to chat via Telegram HTTP API (simple photo send)
    if err := images.SendPhoto(h.cfg.BotToken, p.ChatID, finalURL, "✅"); err != nil {
        return fmt.Errorf("send photo: %w", err)
    }
    if h.db != nil {
        _ = h.db.UpdateGenerationFinal(ctx, p.GID, finalURL)
        if !h.isFreeUser(p.ChatID) { _ = h.db.ConsumeCredit(ctx, p.ChatID) }
    }
    return nil
}

func (h *Handler) isFreeUser(uid int64) bool {
    if h.cfg.AdminIDs != nil && h.cfg.AdminIDs[uid] { return true }
    if h.cfg.WhitelistIDs != nil && h.cfg.WhitelistIDs[uid] { return true }
    if h.db != nil && h.db.IsWhitelisted(context.Background(), uid) { return true }
    return false
}

func (h *Handler) HandlePublish(ctx context.Context, t *asynq.Task) error { return nil }
func (h *Handler) HandleNudge(ctx context.Context, t *asynq.Task) error   { return nil }
