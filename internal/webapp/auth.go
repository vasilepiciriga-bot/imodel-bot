package webapp

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/url"
	"sort"
	"strings"
	"time"
)

type TGUser struct {
	ID        int64  `json:"id"`
	FirstName string `json:"first_name"`
	Username  string `json:"username"`
	Lang      string `json:"language_code"`
}

// ValidateInitData validates Telegram WebApp initData and returns the user.
// Returns error if the signature is invalid or data is expired (>5 min).
func ValidateInitData(initData, botToken string) (TGUser, error) {
	vals, err := url.ParseQuery(initData)
	if err != nil || len(vals) == 0 {
		return TGUser{}, errors.New("invalid initData")
	}

	receivedHash := vals.Get("hash")
	if receivedHash == "" {
		return TGUser{}, errors.New("missing hash")
	}
	vals.Del("hash")

	// Build data_check_string: sorted key=value pairs joined with \n
	pairs := make([]string, 0, len(vals))
	for k, v := range vals {
		pairs = append(pairs, k+"="+v[0])
	}
	sort.Strings(pairs)
	dataCheckString := strings.Join(pairs, "\n")

	// secret_key = HMAC-SHA256(bot_token, "WebAppData")
	mac := hmac.New(sha256.New, []byte("WebAppData"))
	mac.Write([]byte(botToken))
	secretKey := mac.Sum(nil)

	// expected_hash = HMAC-SHA256(data_check_string, secret_key)
	mac2 := hmac.New(sha256.New, secretKey)
	mac2.Write([]byte(dataCheckString))
	expectedHash := hex.EncodeToString(mac2.Sum(nil))

	if !hmac.Equal([]byte(expectedHash), []byte(receivedHash)) {
		return TGUser{}, errors.New("invalid signature")
	}

	// Check auth_date freshness (max 1 hour)
	authDate := vals.Get("auth_date")
	if authDate != "" {
		var ts int64
		for _, c := range authDate {
			if c >= '0' && c <= '9' {
				ts = ts*10 + int64(c-'0')
			}
		}
		if time.Now().Unix()-ts > 3600 {
			return TGUser{}, errors.New("initData expired")
		}
	}

	var user TGUser
	if raw := vals.Get("user"); raw != "" {
		_ = json.Unmarshal([]byte(raw), &user)
	}
	if user.ID == 0 {
		return TGUser{}, errors.New("no user in initData")
	}
	return user, nil
}
