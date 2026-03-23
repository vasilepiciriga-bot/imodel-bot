package main

import (
    "context"
    "fmt"
    "io/ioutil"
    "os"
    "path/filepath"
    "strings"

    "github.com/jackc/pgx/v5"
)

func main() {
    dsn := os.Getenv("DATABASE_URL")
    if dsn == "" { fmt.Println("DATABASE_URL required"); os.Exit(1) }
    ctx := context.Background()
    conn, err := pgx.Connect(ctx, dsn)
    if err != nil { panic(err) }
    defer conn.Close(ctx)
    files, _ := filepath.Glob("migrations/*.sql")
    for _, f := range files {
        b, _ := ioutil.ReadFile(f)
        sql := string(b)
        if i := strings.Index(sql, "-- +goose Down"); i >= 0 { sql = sql[:i] }
        if i := strings.Index(sql, "-- +goose Up"); i >= 0 { sql = sql[i+len("-- +goose Up"):]} 
        if strings.TrimSpace(sql) == "" { continue }
        fmt.Println("Applying", f)
        if _, err := conn.Exec(ctx, sql); err != nil { panic(err) }
    }
    fmt.Println("Migrations applied")
}

