package payments

import (
    "bytes"
    "encoding/json"
    "errors"
    "net/http"
)

type labeledPrice struct{ Label string `json:"label"`; Amount int `json:"amount"` }

type sendInvoiceReq struct {
    ChatID      int64          `json:"chat_id"`
    Title       string         `json:"title"`
    Description string         `json:"description"`
    Payload     string         `json:"payload"`
    Currency    string         `json:"currency"`
    Prices      []labeledPrice `json:"prices"`
}

func SendStarsInvoice(botToken string, chatID int64, title, description, payload string, stars int) error {
    if botToken == "" { return errors.New("no bot token") }
    body := sendInvoiceReq{
        ChatID: chatID,
        Title: title,
        Description: description,
        Payload: payload,
        Currency: "XTR",
        Prices: []labeledPrice{{Label: "iModel Credits", Amount: stars}},
    }
    b, _ := json.Marshal(body)
    req, _ := http.NewRequest(http.MethodPost, "https://api.telegram.org/bot"+botToken+"/sendInvoice", bytes.NewReader(b))
    req.Header.Set("Content-Type", "application/json")
    resp, err := http.DefaultClient.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode >= 300 { return errors.New("sendInvoice failed") }
    return nil
}

type sendSubInvoiceReq struct {
    ChatID             int64          `json:"chat_id"`
    Title              string         `json:"title"`
    Description        string         `json:"description"`
    Payload            string         `json:"payload"`
    Currency           string         `json:"currency"`
    Prices             []labeledPrice `json:"prices"`
    SubscriptionPeriod int            `json:"subscription_period"` // seconds; 2592000 = 30 days
}

// SendSubscriptionInvoice sends a recurring monthly Stars invoice.
func SendSubscriptionInvoice(botToken string, chatID int64, title, description, payload string, stars int) error {
    if botToken == "" { return errors.New("no bot token") }
    body := sendSubInvoiceReq{
        ChatID:             chatID,
        Title:              title,
        Description:        description,
        Payload:            payload,
        Currency:           "XTR",
        Prices:             []labeledPrice{{Label: title, Amount: stars}},
        SubscriptionPeriod: 2592000, // 30 days
    }
    b, _ := json.Marshal(body)
    req, _ := http.NewRequest(http.MethodPost, "https://api.telegram.org/bot"+botToken+"/sendInvoice", bytes.NewReader(b))
    req.Header.Set("Content-Type", "application/json")
    resp, err := http.DefaultClient.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode >= 300 { return errors.New("sendInvoice (sub) failed") }
    return nil
}

type preCheckoutReq struct {
    ID  string `json:"pre_checkout_query_id"`
    OK  bool   `json:"ok"`
    Err string `json:"error_message,omitempty"`
}

func AnswerPreCheckout(botToken string, id string, ok bool, errMsg string) error {
    if botToken == "" { return errors.New("no bot token") }
    body := preCheckoutReq{ID: id, OK: ok, Err: errMsg}
    b, _ := json.Marshal(body)
    req, _ := http.NewRequest(http.MethodPost, "https://api.telegram.org/bot"+botToken+"/answerPreCheckoutQuery", bytes.NewReader(b))
    req.Header.Set("Content-Type", "application/json")
    resp, err := http.DefaultClient.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode >= 300 { return errors.New("answerPreCheckout failed") }
    return nil
}
