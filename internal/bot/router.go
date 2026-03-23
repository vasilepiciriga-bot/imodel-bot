package bot

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
    "strings"

    "github.com/hibiken/asynq"
    "imodel-bot/internal/config"
    "imodel-bot/internal/i18n"
    "imodel-bot/internal/log"
    "imodel-bot/internal/services/queue"
)

// HandleUpdate routes raw Telegram update JSON.
func HandleUpdate(ctx context.Context, cfg config.Config, log ilog.Logger, client *asynq.Client, raw map[string]any) error {
	// Minimal: handle /start, /help, text + photo messages by detecting keys without full Telebot.
	if msg, ok := raw["message"].(map[string]any); ok {
		chatID := int64FromPath(msg, "chat", "id")
		text := strFrom(msg, "text")
		if strings.HasPrefix(text, "/start") {
			return sendText(cfg.BotToken, chatID, i18n.T("en", "onboard_welcome"))
		}
		if strings.HasPrefix(text, "/help") {
			return sendText(cfg.BotToken, chatID, i18n.T("en", "help"))
		}
		// If has caption and photo → treat as prompt + selfie
		caption := strFrom(msg, "caption")
		if caption != "" && hasPhotos(msg) {
			gid := newID()
			_, err := queue.EnqueueGenerate(ctx, client, queue.GeneratePayload{
				GID: gid, ChatID: chatID, Mode: "normal", Prompt: caption,
			})
			if err != nil { return err }
			return sendText(cfg.BotToken, chatID, i18n.T("en", "gen"))
		}
		// Pure text prompt
		if text != "" {
			gid := newID()
			_, err := queue.EnqueueGenerate(ctx, client, queue.GeneratePayload{GID: gid, ChatID: chatID, Mode: "normal", Prompt: text})
			if err != nil { return err }
			return sendText(cfg.BotToken, chatID, i18n.T("en", "gen"))
		}
	}
	return nil
}

func int64FromPath(m map[string]any, path ...string) int64 {
	x := m
	for i, p := range path {
		if i == len(path)-1 { if v, ok := x[p].(float64); ok { return int64(v) } }
		n, _ := x[p].(map[string]any); x = n
	}
	return 0
}

func strFrom(m map[string]any, k string) string {
	if v, ok := m[k].(string); ok { return v }
	return ""
}

func hasPhotos(msg map[string]any) bool {
	if _, ok := msg["photo"]; ok { return true }
	return false
}

func sendText(botToken string, chatID int64, text string) error {
	b, _ := json.Marshal(map[string]any{"chat_id": chatID, "text": text})
	resp, err := httpPost("https://api.telegram.org/bot"+botToken+"/sendMessage", b)
	_ = resp
	return err
}

func newID() string { return fmt.Sprintf("%d", timeNowUnix()) }

var timeNowUnix = func() int64 { return time.Now().UnixNano() }

// tiny HTTP POST helper
func httpPost(url string, body []byte) (*http.Response, error) {
	req, _ := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil { return nil, err }
	if resp.StatusCode >= 300 { return resp, fmt.Errorf("bad status: %s", resp.Status) }
	return resp, nil
}
