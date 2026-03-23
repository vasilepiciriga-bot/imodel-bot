package repo

import (
    "context"
    "time"
)

type WhitelistItem struct {
    TGID     int64     `json:"tg_id"`
    Username string    `json:"username"`
    LastSeen time.Time `json:"last_seen"`
}

func (s *Store) ListWhitelist(ctx context.Context, offset, limit int) ([]WhitelistItem, int, error) {
    if s.DB == nil { return []WhitelistItem{}, 0, nil }
    rows, err := s.DB.Query(ctx, `select tg_id, coalesce(username,''), coalesce(last_seen, now()) from users where is_whitelist is true order by last_seen desc offset $1 limit $2`, offset, limit)
    if err != nil { return nil, 0, err }
    defer rows.Close()
    out := []WhitelistItem{}
    for rows.Next() {
        var it WhitelistItem
        if err := rows.Scan(&it.TGID, &it.Username, &it.LastSeen); err != nil { return nil, 0, err }
        out = append(out, it)
    }
    var total int
    if err := s.DB.QueryRow(ctx, `select count(1) from users where is_whitelist is true`).Scan(&total); err != nil { total = 0 }
    return out, total, nil
}

type UserInfo struct {
    TGID      int64  `json:"tg_id"`
    Username  string `json:"username"`
    Lang      string `json:"lang"`
    Credits   int    `json:"credits"`
    Whitelist bool   `json:"is_whitelist"`
}

func (s *Store) GetUserInfo(ctx context.Context, tgID int64) (UserInfo, error) {
    var u UserInfo
    if s.DB == nil { return u, nil }
    err := s.DB.QueryRow(ctx, `select tg_id, coalesce(username,''), coalesce(nullif(lang,''),'en'), coalesce(credits,0), coalesce(is_whitelist,false) from users where tg_id=$1`, tgID).Scan(&u.TGID, &u.Username, &u.Lang, &u.Credits, &u.Whitelist)
    return u, err
}

