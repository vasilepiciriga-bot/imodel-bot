package repo

import "context"

func (s *Store) ListUserGenerationsFinal(ctx context.Context, tgID int64, limit int) ([]string, error) {
	if s.DB == nil { return []string{}, nil }
	rows, err := s.DB.Query(ctx, `select final_url from generations where user_id=$1 and final_url is not null and final_url <> '' order by created_at desc limit $2`, tgID, limit)
	if err != nil { return nil, err }
	defer rows.Close()
	var out []string
	for rows.Next() {
		var u string
		if err := rows.Scan(&u); err != nil { return nil, err }
		out = append(out, u)
	}
	return out, nil
}

func (s *Store) ListUserGenerationsFinalPaged(ctx context.Context, tgID int64, offset, limit int) ([]string, error) {
    if s.DB == nil { return []string{}, nil }
    rows, err := s.DB.Query(ctx, `select final_url from generations where user_id=$1 and final_url is not null and final_url <> '' order by created_at desc offset $2 limit $3`, tgID, offset, limit)
    if err != nil { return nil, err }
    defer rows.Close()
    var out []string
    for rows.Next() {
        var u string
        if err := rows.Scan(&u); err != nil { return nil, err }
        out = append(out, u)
    }
    return out, nil
}

func (s *Store) CountUserGenerationsFinal(ctx context.Context, tgID int64) (int, error) {
    if s.DB == nil { return 0, nil }
    var n int
    err := s.DB.QueryRow(ctx, `select count(1) from generations where user_id=$1 and final_url is not null and final_url <> ''`, tgID).Scan(&n)
    if err != nil { return 0, err }
    return n, nil
}
