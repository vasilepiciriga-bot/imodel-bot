package ilog

import (
	"log/slog"
	"os"
)

type Logger = *slog.Logger

func New(env string) Logger {
	lvl := new(slog.LevelVar)
	if env == "dev" {
		lvl.Set(slog.LevelDebug)
	} else {
		lvl.Set(slog.LevelInfo)
	}
	h := slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: lvl})
	return slog.New(h)
}
