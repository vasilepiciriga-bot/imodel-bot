package openai

import (
    "bytes"
    "context"
    "encoding/json"
    "errors"
    "net/http"
    "strings"
)

type Client struct{ apiKey string; http *http.Client; model string }

func New(apiKey string) *Client {
    if apiKey == "" { return nil }
    return &Client{apiKey: apiKey, http: &http.Client{}, model: "gpt-4o-mini"}
}

func (c *Client) WithModel(m string) *Client { if m != "" { c.model = m }; return c }

type msg struct{ Role string `json:"role"`; Content any `json:"content"` }

// CraftPromptFromStyle calls Chat Completions with an image_url to produce JSON {prompt,negative,seed_hint}.
func (c *Client) CraftPromptFromStyle(ctx context.Context, styleURL string) (prompt, negative, seed string, err error) {
    if c == nil { return "", "", "", errors.New("openai not configured") }
    sys := `You are a prompt engineer for a portrait AI model (similar to face-swap + style transfer). ` +
        `The model takes a selfie and a style image and generates a photorealistic portrait. ` +
        `Analyze the style image and return ONLY a JSON object with these fields:` + "\n" +
        `- prompt: describe the scene/setting/lighting/lens in photography terms (e.g. "outdoor golden hour portrait, 85mm f/1.4, warm rim light, bokeh background, skin texture visible"). Focus on environment, lighting, mood — NOT on the person's identity.` + "\n" +
        `- negative: comma-separated list of things to avoid (deformed face, blurry, low-res, watermark, text, cgi, cartoon, extra fingers, bad anatomy, overexposed, underexposed, jpeg artifacts).` + "\n" +
        `- seed_hint: a short word describing the dominant color palette or mood (e.g. "warm", "cool", "dramatic", "pastel").` + "\n" +
        `Return ONLY valid JSON, no markdown, no explanation.`
    u := map[string]any{
        "model": c.model,
        "messages": []msg{
            {Role: "system", Content: sys},
            {Role: "user", Content: []map[string]any{
                {"type": "text", "text": "Analyze this style photo and return JSON {prompt, negative, seed_hint}."},
                {"type": "image_url", "image_url": map[string]any{"url": styleURL, "detail": "high"}},
            }},
        },
        "temperature": 0.2,
        "max_tokens": 500,
    }
    b, _ := json.Marshal(u)
    req, _ := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.openai.com/v1/chat/completions", bytes.NewReader(b))
    req.Header.Set("Authorization", "Bearer "+c.apiKey)
    req.Header.Set("Content-Type", "application/json")
    resp, err := c.http.Do(req)
    if err != nil { return "", "", "", err }
    defer resp.Body.Close()
    var out struct{ Choices []struct{ Message struct{ Content string `json:"content"` } `json:"message"` } `json:"choices"` }
    if err := json.NewDecoder(resp.Body).Decode(&out); err != nil { return "", "", "", err }
    if len(out.Choices) == 0 { return "", "", "", errors.New("no choices") }
    raw := strings.TrimSpace(out.Choices[0].Message.Content)
    var data struct{ Prompt, Negative, SeedHint string `json:"prompt"` }
    // flexible decode: try map first
    var m map[string]any
    if json.Unmarshal([]byte(raw), &m) == nil {
        if v, ok := m["prompt"].(string); ok { data.Prompt = v }
        if v, ok := m["negative"].(string); ok { data.Negative = v }
        if v, ok := m["seed_hint"].(string); ok { data.SeedHint = v }
    } else {
        // fallback defaults
        data.Prompt = "photorealistic portrait, natural lighting, 85mm lens, shallow depth of field, sharp eyes"
        data.Negative = "deformed face, disfigured, blurry, low-res, watermark, text, cgi, cartoon, extra fingers, bad anatomy"
        data.SeedHint = "natural"
    }
    if data.Prompt == "" { data.Prompt = "photorealistic portrait, natural lighting, 85mm lens, shallow depth of field, sharp eyes" }
    if data.Negative == "" { data.Negative = "deformed face, disfigured, blurry, low-res, watermark, text, cgi, cartoon, extra fingers, bad anatomy" }
    if data.SeedHint == "" { data.SeedHint = "natural" }
    return data.Prompt, data.Negative, data.SeedHint, nil
}
