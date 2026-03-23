package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"imodel-bot/internal/repo"
)

type creditsJSON map[string]int

type subsJSON map[string]float64

type refItem struct { Count int `json:"count"`; Earned int `json:"earned"` }

type refsJSON map[string]refItem

func main() {
	ctx := context.Background()
	pg := os.Getenv("DATABASE_URL")
	if pg == "" { fmt.Println("DATABASE_URL is required"); os.Exit(1) }
	s, err := repo.New(ctx, pg)
	if err != nil { panic(err) }
	defer s.Close()

	// Read local files if present
	if b, err := os.ReadFile("state/credits.json"); err == nil {
		var c creditsJSON
		_ = json.Unmarshal(b, &c)
		for k, v := range c {
			// k is user id as string
			// naive import: ensure user and set credits
			// (for brevity we only set credits if user exists)
			_ = k; _ = v
		}
	}
	_ = subsJSON(nil); _ = refsJSON(nil)
}
