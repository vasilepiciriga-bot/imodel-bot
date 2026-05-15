package config

import (
	"log"
	"os"
	"strconv"
)

type Config struct {
    Env            string
    BotToken       string
    WebhookSecret  string
    PublicURL      string
    AdminSecret    string
    AdminIDs       map[int64]bool
    WhitelistIDs   map[int64]bool
    AdminBasicUser string
    AdminBasicPass string

	RedisAddr      string
	RedisPassword  string
	RedisDB        int

	PostgresURL    string

	S3Endpoint     string
	S3Region       string
	S3Bucket       string
	S3KeyID        string
	S3Secret       string

	OpenAIKey      string
	OpenAIModel    string
	OpenAIVision   string

	ReplicateToken string
	NanoBanana     string
	ESRGAN         string

	PreviewFirst   bool
	WorkerConcurrency int
}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" { return v }
	return def
}

func getint(key string, def int) int {
	v := os.Getenv(key)
	if v == "" { return def }
	i, err := strconv.Atoi(v)
	if err != nil { return def }
	return i
}

func getbool(key string, def bool) bool {
	v := os.Getenv(key)
	if v == "" { return def }
	if v == "1" || v == "true" || v == "TRUE" { return true }
	if v == "0" || v == "false" || v == "FALSE" { return false }
	return def
}

func Load() Config {
    cfg := Config{
        Env:           getenv("ENV", "prod"),
        BotToken:      getenv("BOT_TOKEN", ""),
        WebhookSecret: getenv("WEBHOOK_SECRET", ""),
        PublicURL:     getenv("PUBLIC_URL", ""),
        AdminSecret:   getenv("ADMIN_PANEL_SECRET", getenv("METRICS_SECRET", "")),
        AdminIDs:      parseIDs(getenv("ADMIN_IDS", "")),
        WhitelistIDs:  parseIDs(getenv("WHITELIST_IDS", "")),
        AdminBasicUser: getenv("ADMIN_BASIC_USER", ""),
        AdminBasicPass: getenv("ADMIN_BASIC_PASS", ""),

		RedisAddr:     getenv("REDIS_ADDR", getenv("REDIS_URL", "127.0.0.1:6379")),
		RedisPassword: getenv("REDIS_PASSWORD", ""),
		RedisDB:       getint("REDIS_DB", 0),

		PostgresURL:   getenv("DATABASE_URL", getenv("POSTGRES_URL", "")),

		S3Endpoint:    getenv("S3_ENDPOINT", ""),
		S3Region:      getenv("S3_REGION", ""),
		S3Bucket:      getenv("S3_BUCKET", ""),
		S3KeyID:       getenv("S3_ACCESS_KEY_ID", ""),
		S3Secret:      getenv("S3_SECRET_ACCESS_KEY", ""),

		OpenAIKey:     getenv("OPENAI_API_KEY", ""),
		OpenAIModel:   getenv("OPENAI_MODEL", "gpt-4o-mini"),
		OpenAIVision:  getenv("OPENAI_MODEL_VISION", getenv("OPENAI_MODEL", "gpt-4o-mini")),

		ReplicateToken: getenv("REPLICATE_API_TOKEN", ""),
		NanoBanana:     getenv("NANOBANANA_MODEL", "google/nano-banana"),
		ESRGAN:         getenv("ESRGAN_MODEL", "nightmareai/real-esrgan"),

		PreviewFirst:    getbool("PREVIEW_FIRST", true),
		WorkerConcurrency: getint("WORKER_CONCURRENCY", 20),
	}
	if cfg.BotToken == "" { log.Println("WARN: BOT_TOKEN is empty") }
	return cfg
}

func parseIDs(s string) map[int64]bool {
    out := map[int64]bool{}
    if s == "" { return out }
    cur := int64(0)
    neg := false
    have := false
    flush := func(){ if have { if neg { cur = -cur }; out[cur] = true }; cur = 0; neg = false; have = false }
    for i := 0; i < len(s); i++ {
        c := s[i]
        if c >= '0' && c <= '9' { cur = cur*10 + int64(c-'0'); have = true; continue }
        if c == '-' && !have { neg = true; continue }
        // delimiter
        flush()
    }
    flush()
    return out
}
