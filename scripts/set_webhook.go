package main

import (
    "bytes"
    "encoding/json"
    "flag"
    "fmt"
    "net/http"
    "os"
)

func main() {
    token := envOr("BOT_TOKEN", "")
    url := envOr("WEBHOOK_URL", "")
    secret := envOr("WEBHOOK_SECRET", "")
    flag.StringVar(&token, "token", token, "bot token")
    flag.StringVar(&url, "url", url, "public webhook url")
    flag.StringVar(&secret, "secret", secret, "secret token")
    flag.Parse()
    if token == "" || url == "" { fmt.Println("token and url required"); os.Exit(1) }
    body := map[string]any{"url": url}
    if secret != "" { body["secret_token"] = secret }
    b, _ := json.Marshal(body)
    resp, err := http.Post("https://api.telegram.org/bot"+token+"/setWebhook", "application/json", bytes.NewReader(b))
    if err != nil { panic(err) }
    defer resp.Body.Close()
    fmt.Println("status:", resp.Status)
}

func envOr(k, d string) string { v := os.Getenv(k); if v == "" { return d }; return v }

