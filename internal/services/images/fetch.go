package images

import (
	"bytes"
	"context"
	"errors"
	"io"
	"mime"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

var httpc = &http.Client{ Timeout: 30 * time.Second }

func Download(ctx context.Context, u string, max int64) ([]byte, string, error) {
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	resp, err := httpc.Do(req)
	if err != nil { return nil, "", err }
	defer resp.Body.Close()
	if resp.StatusCode != 200 { return nil, "", errors.New("bad status") }
	var buf bytes.Buffer
	if max <= 0 { max = 15 << 20 }
	_, err = io.Copy(&buf, io.LimitReader(resp.Body, max))
	if err != nil { return nil, "", err }
	ct := resp.Header.Get("Content-Type")
	if ct == "" { ct = mime.TypeByExtension(".jpg") }
	return buf.Bytes(), ct, nil
}

func SendMessage(botToken string, chatID int64, text string) error {
	if botToken == "" { return errors.New("no bot token") }
	v := url.Values{}
	v.Set("chat_id", strconv.FormatInt(chatID, 10))
	v.Set("text", text)
	req, _ := http.NewRequest(http.MethodPost, "https://api.telegram.org/bot"+botToken+"/sendMessage", bytes.NewBufferString(v.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := httpc.Do(req)
	if err != nil { return err }
	defer resp.Body.Close()
	if resp.StatusCode != 200 { return errors.New("telegram sendMessage failed") }
	return nil
}

func SendPhoto(botToken string, chatID int64, photoURL string, caption string) error {
	if botToken == "" { return errors.New("no bot token") }
	v := url.Values{}
	v.Set("chat_id", strconv.FormatInt(chatID, 10))
	v.Set("photo", photoURL)
	if caption != "" { v.Set("caption", caption) }
	req, _ := http.NewRequest(http.MethodPost, "https://api.telegram.org/bot"+botToken+"/sendPhoto", bytes.NewBufferString(v.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := httpc.Do(req)
	if err != nil { return err }
	defer resp.Body.Close()
	if resp.StatusCode != 200 { return errors.New("telegram sendPhoto failed") }
	return nil
}
