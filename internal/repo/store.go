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

// ClaimStartBonus atomically gives 1 credit on first /start. Returns true if credit was granted.
func (s *Store) ClaimStartBonus(ctx context.Context, tgID int64) (bool, error) {
    if s.DB == nil { return false, nil }
    tag, err := s.DB.Exec(ctx, `
        update users set credits = coalesce(credits,0) + 1, start_bonus_claimed = true
        where tg_id = $1 and coalesce(start_bonus_claimed, false) = false
    `, tgID)
    if err != nil { return false, err }
    return tag.RowsAffected() > 0, nil
}

// GetSubTier returns the user's active subscription tier ("basic", "pro", "unlimited") or "".
func (s *Store) GetSubTier(ctx context.Context, tgID int64) string {
    if s.DB == nil { return "" }
    var tier string
    err := s.DB.QueryRow(ctx, `
        select coalesce(nullif(sub_tier,''),'') from users
        where tg_id = $1 and sub_until > now()
    `, tgID).Scan(&tier)
    if err != nil { return "" }
    return tier
}

// SetSubscription activates a subscription tier for 30 days and adds credits.
// For unlimited tier pass credits = -1 to skip credit addition.
func (s *Store) SetSubscription(ctx context.Context, tgID int64, tier string, credits int, stars int, payload string) error {
    if s.DB == nil { return nil }
    tx, err := s.DB.Begin(ctx)
    if err != nil { return err }
    defer tx.Rollback(ctx)
    _, err = tx.Exec(ctx, `
        update users set sub_tier = $2, sub_until = now() + interval '30 days'
        where tg_id = $1
    `, tgID, tier)
    if err != nil { return err }
    if credits > 0 {
        _, err = tx.Exec(ctx, `update users set credits = coalesce(credits,0) + $2 where tg_id = $1`, tgID, credits)
        if err != nil { return err }
    }
    _, err = tx.Exec(ctx, `
        insert into subscription_events(user_id, tier, stars, payload) values($1,$2,$3,$4)
    `, tgID, tier, stars, payload)
    if err != nil { return err }
    return tx.Commit(ctx)
}

// HasUnlimitedSub returns true if user has an active unlimited subscription.
func (s *Store) HasUnlimitedSub(ctx context.Context, tgID int64) bool {
    return s.GetSubTier(ctx, tgID) == "unlimited"
}

// PayReferralBonus gives +3 credits to the referrer on the referred user's first purchase.
// Safe to call multiple times — bonus is only paid once per referral.
func (s *Store) PayReferralBonus(ctx context.Context, userID int64) error {
    if s.DB == nil { return nil }
    tx, err := s.DB.Begin(ctx)
    if err != nil { return err }
    defer tx.Rollback(ctx)
    var referrerID int64
    err = tx.QueryRow(ctx, `
        select referrer_id from referrals
        where user_id = $1 and coalesce(bonus_paid, false) = false and referrer_id is not null
    `, userID).Scan(&referrerID)
    if err != nil { return nil } // no referral or already paid — not an error
    _, err = tx.Exec(ctx, `update users set credits = coalesce(credits,0) + 3 where tg_id = $1`, referrerID)
    if err != nil { return err }
    _, err = tx.Exec(ctx, `update referrals set bonus_paid = true where user_id = $1`, userID)
    if err != nil { return err }
    return tx.Commit(ctx)
}
