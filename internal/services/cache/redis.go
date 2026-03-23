package cache

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"
)

type Cache struct{ R *redis.Client }

func New(addr string, pass string, db int) *Cache {
	if addr == "" { return nil }
	return &Cache{R: redis.NewClient(&redis.Options{Addr: addr, Password: pass, DB: db})}
}

func (c *Cache) SetJSON(ctx context.Context, key string, val string, ttl time.Duration) error {
	if c == nil { return nil }
	return c.R.Set(ctx, key, val, ttl).Err()
}

func (c *Cache) Get(ctx context.Context, key string) (string, error) {
	if c == nil { return "", nil }
	return c.R.Get(ctx, key).Result()
}
