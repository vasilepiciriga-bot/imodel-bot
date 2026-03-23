package queue

import (
	"context"
	"encoding/json"

	"github.com/hibiken/asynq"
)

const (
	TypeGenerate = "imodel:generate"
	TypeUpscale  = "imodel:upscale"
	TypePublish  = "imodel:publish"
	TypeNudge    = "imodel:nudge"

	QueueDefault  = "default"
	QueueCritical = "critical"
)

type GeneratePayload struct {
	GID      string `json:"gid"`
	ChatID   int64  `json:"chat_id"`
	Mode     string `json:"mode"`
	Prompt   string `json:"prompt"`
	Negative string `json:"negative"`
	Seed     string `json:"seed"`
	SelfieURL string `json:"selfie_url"`
	StyleURL  string `json:"style_url"`
}

type UpscalePayload struct {
	GID    string `json:"gid"`
	ChatID int64  `json:"chat_id"`
	URL    string `json:"url"`
}

type PublishPayload struct {
	ChatID int64  `json:"chat_id"`
	URL    string `json:"url"`
	Caption string `json:"caption"`
}

type NudgePayload struct {
	ChatID int64 `json:"chat_id"`
	Text   string `json:"text"`
}

func EnqueueGenerate(ctx context.Context, c *asynq.Client, p GeneratePayload) (*asynq.TaskInfo, error) {
	b, _ := json.Marshal(p)
	t := asynq.NewTask(TypeGenerate, b, asynq.Queue(QueueCritical))
	return c.EnqueueContext(ctx, t)
}

func EnqueueUpscale(ctx context.Context, c *asynq.Client, p UpscalePayload) (*asynq.TaskInfo, error) {
	b, _ := json.Marshal(p)
	t := asynq.NewTask(TypeUpscale, b, asynq.Queue(QueueDefault))
	return c.EnqueueContext(ctx, t)
}

func EnqueuePublish(ctx context.Context, c *asynq.Client, p PublishPayload) (*asynq.TaskInfo, error) {
	b, _ := json.Marshal(p)
	t := asynq.NewTask(TypePublish, b, asynq.Queue(QueueDefault))
	return c.EnqueueContext(ctx, t)
}

func EnqueueNudge(ctx context.Context, c *asynq.Client, p NudgePayload) (*asynq.TaskInfo, error) {
	b, _ := json.Marshal(p)
	t := asynq.NewTask(TypeNudge, b, asynq.Queue(QueueDefault))
	return c.EnqueueContext(ctx, t)
}
