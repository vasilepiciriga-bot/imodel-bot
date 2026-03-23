package images

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
)

type getFileResp struct {
	OK     bool `json:"ok"`
	Result struct {
		FileID   string `json:"file_id"`
		FilePath string `json:"file_path"`
	} `json:"result"`
}

// GetFileURL resolves a Telegram file_id to a direct HTTPS URL.
func GetFileURL(botToken string, fileID string) (string, error) {
	if botToken == "" || fileID == "" { return "", errors.New("missing") }
	u := "https://api.telegram.org/bot" + url.PathEscape(botToken) + "/getFile?file_id=" + url.QueryEscape(fileID)
	resp, err := http.Get(u)
	if err != nil { return "", err }
	defer resp.Body.Close()
	var r getFileResp
	if err := json.NewDecoder(resp.Body).Decode(&r); err != nil { return "", err }
	if !r.OK || r.Result.FilePath == "" { return "", errors.New("tg getFile failed") }
	return "https://api.telegram.org/file/bot" + botToken + "/" + r.Result.FilePath, nil
}
