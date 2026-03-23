package replicate

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"time"
)

type Client struct { token string; http *http.Client }

func New(token string) *Client {
	if token == "" { return nil }
	return &Client{ token: token, http: &http.Client{ Timeout: 60 * time.Second } }
}

type predictionReq struct {
	Version string         `json:"version,omitempty"`
	Input   map[string]any `json:"input"`
}

type predictionResp struct {
	ID     string `json:"id"`
	Status string `json:"status"`
	Error  any    `json:"error"`
	Output any    `json:"output"`
}

func (c *Client) Generate(ctx context.Context, model string, input map[string]any) (string, error) {
	// Create prediction
	body, _ := json.Marshal(predictionReq{Input: input})
	req, _ := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.replicate.com/v1/models/"+model+"/predictions", bytes.NewReader(body))
	req.Header.Set("Authorization", "Token "+c.token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil { return "", err }
	defer resp.Body.Close()
	if resp.StatusCode >= 300 { return "", errors.New("replicate create failed") }
	var pr predictionResp
	if err := json.NewDecoder(resp.Body).Decode(&pr); err != nil { return "", err }
	id := pr.ID
	// Poll
	for i:=0; i<120; i++ {
		req2, _ := http.NewRequestWithContext(ctx, http.MethodGet, "https://api.replicate.com/v1/predictions/"+id, nil)
		req2.Header.Set("Authorization", "Token "+c.token)
		resp2, err := c.http.Do(req2)
		if err != nil { return "", err }
		var pr2 predictionResp
		_ = json.NewDecoder(resp2.Body).Decode(&pr2); resp2.Body.Close()
		if pr2.Status == "succeeded" {
			// Expect output as URL or [URL]
			switch v := pr2.Output.(type) {
			case string:
				return v, nil
			case []any:
				if len(v) > 0 {
					if s, ok := v[0].(string); ok { return s, nil }
				}
			}
			return "", errors.New("replicate: unexpected output")
		}
		if pr2.Status == "failed" || pr2.Status == "canceled" {
			return "", errors.New("replicate failed")
		}
		time.Sleep(2 * time.Second)
	}
	return "", errors.New("replicate timeout")
}
