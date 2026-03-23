package domain

import "time"

type Mode string

const (
	ModeNormal Mode = "normal"
	ModeCopy   Mode = "copy"
)

type GenerationStatus string

const (
	GenQueued   GenerationStatus = "queued"
	GenRunning  GenerationStatus = "running"
	GenFailed   GenerationStatus = "failed"
	GenDone     GenerationStatus = "done"
)

type User struct {
	TGID         int64
	Username     string
	Lang         string
	FirstSeen    time.Time
	LastSeen     time.Time
	Sessions     int
	Messages     int
	Photos       int
	GensOK       int
	GensFail     int
	PremiumUntil *time.Time
	Credits      int
}

type Generation struct {
	ID          string
	UserID      int64
	Mode        Mode
	Preset      string
	Prompt      string
	Negative    string
	Seed        string
	StyleURL    string
	SelfieURL   string
	PreviewURL  string
	FinalURL    string
	ReplicateID string
	Status      GenerationStatus
	CreatedAt   time.Time
}
