package repo

import (
    "context"
)

type DailyRow struct {
    Day        string `json:"day"`
    Updates    int    `json:"updates"`
    Messages   int    `json:"messages"`
    Photos     int    `json:"photos"`
    GensOK     int    `json:"gens_ok"`
    GensFail   int    `json:"gens_fail"`
    Previews   int    `json:"previews"`
    Finals     int    `json:"finals"`
    Payments   int    `json:"payments"`
    PromoUsed  int    `json:"promo_used"`
    Referrals  int    `json:"referrals"`
}

func (s *Store) ListStatsDaily(ctx context.Context, limit int) ([]DailyRow, error) {
    if s.DB == nil { return []DailyRow{}, nil }
    rows, err := s.DB.Query(ctx, `select day, updates, messages, photos, gens_ok, gens_fail, previews, finals, payments, promo_used, referrals from stats_daily order by day desc limit $1`, limit)
    if err != nil { return nil, err }
    defer rows.Close()
    out := []DailyRow{}
    for rows.Next() {
        var r DailyRow
        if err := rows.Scan(&r.Day, &r.Updates, &r.Messages, &r.Photos, &r.GensOK, &r.GensFail, &r.Previews, &r.Finals, &r.Payments, &r.PromoUsed, &r.Referrals); err != nil { return nil, err }
        out = append(out, r)
    }
    return out, nil
}

