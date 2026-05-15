package webapp

import (
	"context"
	"encoding/base64"
	"fmt"
	"net/http"
	"time"

	"github.com/gofiber/fiber/v2"
	"imodel-bot/internal/config"
	"imodel-bot/internal/domain"
	"imodel-bot/internal/repo"
	"imodel-bot/internal/services/queue"
	"imodel-bot/internal/services/storage"

	"github.com/hibiken/asynq"
)

// Register mounts all /app/* routes on the given Fiber app.
func Register(app *fiber.App, cfg config.Config, store *repo.Store, asynqCli *asynq.Client) {
	s3 := storage.New(cfg)

	// Serve Mini App HTML
	app.Get("/app", func(c *fiber.Ctx) error {
		return c.Type("html").SendString(miniAppHTML())
	})

	api := app.Group("/app/api")

	// Auth middleware: validates X-Telegram-Init-Data header, injects user into locals
	api.Use(func(c *fiber.Ctx) error {
		initData := c.Get("X-Telegram-Init-Data")
		if initData == "" {
			// dev shortcut: allow ?tg_id=123 when ENV=dev
			if cfg.Env == "dev" {
				c.Locals("uid", int64(0))
				return c.Next()
			}
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{"error": "missing initData"})
		}
		user, err := ValidateInitData(initData, cfg.BotToken)
		if err != nil {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{"error": err.Error()})
		}
		c.Locals("uid", user.ID)
		c.Locals("tguser", user)
		// Ensure user exists in DB
		if store != nil {
			_ = store.EnsureUser(context.Background(), user.ID, user.Username, user.Lang)
		}
		return c.Next()
	})

	// GET /app/api/me — credits, plan, username
	api.Get("/me", func(c *fiber.Ctx) error {
		uid := c.Locals("uid").(int64)
		credits := 0
		subTier := ""
		if store != nil {
			credits, _ = store.GetCredits(context.Background(), uid)
			subTier = store.GetSubTier(context.Background(), uid)
		}
		tguser, _ := c.Locals("tguser").(TGUser)
		return c.JSON(fiber.Map{
			"id":       uid,
			"name":     tguser.FirstName,
			"username": tguser.Username,
			"credits":  credits,
			"sub_tier": subTier,
		})
	})

	// GET /app/api/presets — list all presets
	api.Get("/presets", func(c *fiber.Ctx) error {
		type presetResp struct {
			Key    string `json:"key"`
			Label  string `json:"label"`
			Prompt string `json:"prompt"`
		}
		out := make([]presetResp, 0, len(domain.Presets))
		for _, p := range domain.Presets {
			out = append(out, presetResp{Key: p.Key, Label: p.Label, Prompt: p.Prompt})
		}
		return c.JSON(out)
	})

	// GET /app/api/gallery?page=0 — paginated gallery
	api.Get("/gallery", func(c *fiber.Ctx) error {
		uid := c.Locals("uid").(int64)
		page := c.QueryInt("page", 0)
		const pageSize = 9
		offset := page * pageSize
		if store == nil {
			return c.JSON(fiber.Map{"items": []string{}, "total": 0})
		}
		total, _ := store.CountUserGenerationsFinal(context.Background(), uid)
		items, _ := store.ListUserGenerationsFinalPaged(context.Background(), uid, offset, pageSize)
		if items == nil {
			items = []string{}
		}
		return c.JSON(fiber.Map{"items": items, "total": total, "page": page})
	})

	// POST /app/api/generate — {preset_key, selfie_b64, prompt}
	api.Post("/generate", func(c *fiber.Ctx) error {
		uid := c.Locals("uid").(int64)

		// credit check
		if store != nil {
			subTier := store.GetSubTier(context.Background(), uid)
			if subTier != "unlimited" {
				n, _ := store.GetCredits(context.Background(), uid)
				if n <= 0 {
					return c.Status(fiber.StatusPaymentRequired).JSON(fiber.Map{
						"error": "No credits. Use /buy in the bot to purchase more.",
					})
				}
			}
		}

		var body struct {
			PresetKey string `json:"preset_key"`
			SelfiEB64 string `json:"selfie_b64"`
			Prompt    string `json:"prompt"`
		}
		if err := c.BodyParser(&body); err != nil {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "bad request"})
		}

		// Resolve prompt + negative
		prompt := body.Prompt
		negative := ""
		if body.PresetKey != "" {
			if p := domain.FindPreset(body.PresetKey); p != nil {
				if prompt == "" {
					prompt = p.Prompt
				}
				negative = p.Negative
			}
		}
		if prompt == "" {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "prompt or preset_key required"})
		}

		// Upload selfie to S3
		selfieURL := ""
		if body.SelfiEB64 != "" {
			imgBytes, err := base64.StdEncoding.DecodeString(body.SelfiEB64)
			if err != nil {
				return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid selfie_b64"})
			}
			if s3 == nil {
				return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
					"error": "S3 not configured. Please use the bot to send photos directly.",
				})
			}
			key := fmt.Sprintf("webapp-uploads/%d/%d.jpg", uid, time.Now().UnixNano())
			ct := http.DetectContentType(imgBytes)
			if err := s3.PutBytes(context.Background(), key, imgBytes, ct); err != nil {
				return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "upload failed"})
			}
			selfieURL, err = s3.PresignGetURL(context.Background(), key, 6*time.Hour)
			if err != nil {
				return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "presign failed"})
			}
		}

		if asynqCli == nil {
			return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{"error": "queue not available"})
		}

		gid := fmt.Sprintf("%d", time.Now().UnixNano())
		payload := queue.GeneratePayload{
			GID:       gid,
			ChatID:    uid,
			Mode:      "normal",
			Prompt:    prompt,
			Negative:  negative,
			SelfieURL: selfieURL,
		}

		subTier := ""
		if store != nil {
			subTier = store.GetSubTier(context.Background(), uid)
		}
		var enqErr error
		if subTier == "pro" || subTier == "unlimited" {
			_, enqErr = queue.EnqueueGeneratePro(context.Background(), asynqCli, payload)
		} else {
			_, enqErr = queue.EnqueueGenerate(context.Background(), asynqCli, payload)
		}
		if enqErr != nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "queue error"})
		}

		return c.JSON(fiber.Map{
			"ok":      true,
			"gid":     gid,
			"message": "Generating… you'll receive the result in the bot shortly.",
		})
	})
}
