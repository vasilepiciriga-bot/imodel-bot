package repo

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Store struct{ DB *pgxpool.Pool }

func New(ctx context.Context, url string) (*Store, error) {
	if url == "" { return &Store{DB: nil}, nil }
	pool, err := pgxpool.New(ctx, url)
	if err != nil { return nil, err }
	return &Store{DB: pool}, nil
}

func (s *Store) Close() { if s.DB != nil { s.DB.Close() } }

func (s *Store) EnsureUser(ctx context.Context, tgID int64, username string, lang string) error {
	if s.DB == nil { return nil }
	_, err := s.DB.Exec(ctx, `
		insert into users(tg_id, username, lang, first_seen, last_seen, sessions)
		values($1,$2,$3, now(), now(), 1)
		on conflict (tg_id) do update set username=excluded.username, last_seen=now();
	`, tgID, username, lang)
	return err
}

func (s *Store) AddCredits(ctx context.Context, tgID int64, n int) error {
	if s.DB == nil { return nil }
	_, err := s.DB.Exec(ctx, `update users set credits = coalesce(credits,0) + $2 where tg_id=$1`, tgID, n)
	return err
}

func (s *Store) GetCredits(ctx context.Context, tgID int64) (int, error) {
    if s.DB == nil { return 0, nil }
    var c int
    err := s.DB.QueryRow(ctx, `select coalesce(credits,0) from users where tg_id=$1`, tgID).Scan(&c)
    if err != nil { return 0, err }
    return c, nil
}

func (s *Store) GetLang(ctx context.Context, tgID int64) (string, error) {
    if s.DB == nil { return "en", nil }
    var lang string
    if err := s.DB.QueryRow(ctx, `select coalesce(nullif(lang,''),'en') from users where tg_id=$1`, tgID).Scan(&lang); err != nil { return "en", err }
    return lang, nil
}

func (s *Store) SetWhitelist(ctx context.Context, tgID int64, v bool) error {
    if s.DB == nil { return nil }
    // ensure user row exists
    _, _ = s.DB.Exec(ctx, `insert into users(tg_id, first_seen, last_seen) values($1, now(), now()) on conflict (tg_id) do nothing`, tgID)
    _, err := s.DB.Exec(ctx, `update users set is_whitelist=$2 where tg_id=$1`, tgID, v)
    return err
}

func (s *Store) IsWhitelisted(ctx context.Context, tgID int64) bool {
    if s.DB == nil { return false }
    var v bool
    if err := s.DB.QueryRow(ctx, `select coalesce(is_whitelist,false) from users where tg_id=$1`, tgID).Scan(&v); err != nil { return false }
    return v
}

func (s *Store) ConsumeCredit(ctx context.Context, tgID int64) error {
	if s.DB == nil { return nil }
	tx, err := s.DB.Begin(ctx)
	if err != nil { return err }
	defer tx.Rollback(ctx)
	var c int
	err = tx.QueryRow(ctx, `select credits from users where tg_id=$1 for update`, tgID).Scan(&c)
	if err != nil { return err }
	if c <= 0 { return errors.New("no_credits") }
	_, err = tx.Exec(ctx, `update users set credits=credits-1 where tg_id=$1`, tgID)
	if err != nil { return err }
	return tx.Commit(ctx)
}

func (s *Store) InsertGeneration(ctx context.Context, gID string, tgID int64, mode, preset, prompt, negative, seed, styleURL, selfieURL string) error {
	if s.DB == nil { return nil }
	_, err := s.DB.Exec(ctx, `
		insert into generations(id, user_id, mode, preset, prompt, negative, seed, style_url, selfie_url, status, created_at)
		values($1,$2,$3,$4,$5,$6,$7,$8,$9,'queued', now())
	`, gID, tgID, mode, preset, prompt, negative, seed, styleURL, selfieURL)
	return err
}

func (s *Store) UpdateGenerationPreview(ctx context.Context, gID, url string) error {
	if s.DB == nil { return nil }
	_, err := s.DB.Exec(ctx, `update generations set preview_url=$2, status='running' where id=$1`, gID, url)
	return err
}

func (s *Store) UpdateGenerationFinal(ctx context.Context, gID, url string) error {
	if s.DB == nil { return nil }
	_, err := s.DB.Exec(ctx, `update generations set final_url=$2, status='done' where id=$1`, gID, url)
	return err
}

func (s *Store) StatsDailyIncr(ctx context.Context, key string, n int) error {
	if s.DB == nil { return nil }
	_, err := s.DB.Exec(ctx, `
		insert into stats_daily(day, ` + key + `) values(current_date, $1)
		on conflict (day) do update set ` + key + ` = coalesce(stats_daily.` + key + `,0) + excluded.` + key + `
	`, n)
	return err
}

func (s *Store) TouchUserActivity(ctx context.Context, tgID int64) error {
    if s.DB == nil { return nil }
    _, err := s.DB.Exec(ctx, `update users set last_seen=now() where tg_id=$1`, tgID)
    return err
}

func (s *Store) Timeout() time.Duration { return 10 * time.Second }

func (s *Store) SetLang(ctx context.Context, tgID int64, lang string) error {
    if s.DB == nil { return nil }
    _, err := s.DB.Exec(ctx, `update users set lang=$2 where tg_id=$1`, tgID, lang)
    return err
}

// CountTable is a helper used by metrics; returns 0 on error.
func (s *Store) CountTable(ctx context.Context, table string) int {
    if s.DB == nil { return 0 }
    var n int
    if err := s.DB.QueryRow(ctx, `select count(1) from `+table).Scan(&n); err != nil { return 0 }
    return n
}

func (s *Store) UpsertReferral(ctx context.Context, userID, referrerID int64) error {
    if s.DB == nil { return nil }
    if userID == referrerID { return nil }
    _, err := s.DB.Exec(ctx, `insert into referrals(user_id, referrer_id) values($1,$2) on conflict(user_id) do nothing`, userID, referrerID)
    return err
}
