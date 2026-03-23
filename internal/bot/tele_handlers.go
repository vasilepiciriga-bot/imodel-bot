package bot

import (
    "context"
    "encoding/json"
    "fmt"
    "strconv"
    "strings"

    "github.com/hibiken/asynq"
    tb "gopkg.in/telebot.v3"
    "imodel-bot/internal/config"
    "imodel-bot/internal/domain"
    "imodel-bot/internal/i18n"
    "imodel-bot/internal/log"
    "imodel-bot/internal/repo"
    "imodel-bot/internal/services/images"
    "imodel-bot/internal/services/openai"
    "imodel-bot/internal/services/payments"
    "imodel-bot/internal/services/queue"
)

var tbot *tb.Bot
var asynqClient *asynq.Client
var appCfg config.Config
var store *repo.Store
var oa *openai.Client

func InitTele(ctx context.Context, cfg config.Config, logger ilog.Logger, client *asynq.Client, st *repo.Store) error {
    if cfg.BotToken == "" { return nil }
    b, err := tb.NewBot(tb.Settings{
        Token:  cfg.BotToken,
        // We do not start the HTTP server here; we only use ProcessUpdate.
        // Poller left nil.
        ParseMode: tb.ModeDefault,
    })
    if err != nil { return err }
    tbot = b
    asynqClient = client
    appCfg = cfg
    store = st
    if cfg.OpenAIKey != "" { oa = openai.New(cfg.OpenAIKey).WithModel(cfg.OpenAIVision) }
    registerHandlers()
    return nil
}

func registerHandlers() {
    if tbot == nil { return }
    tbot.Handle("/start", func(c tb.Context) error {
        // referral: /start <payload>
        if store != nil { _ = store.EnsureUser(context.Background(), c.Sender().ID, c.Sender().Username, "en") }
        parts := strings.Fields(c.Message().Text)
        if len(parts) > 1 && strings.HasPrefix(parts[1], "ref_") {
            refID := atoiSafe(strings.TrimPrefix(parts[1], "ref_"))
            if store != nil { _ = store.UpsertReferral(context.Background(), c.Sender().ID, int64(refID)) }
        }
        lang := getUserLang(c)
        return c.Send(i18n.T(lang, "onboard_welcome"))
    })
    tbot.Handle("/help", func(c tb.Context) error { return c.Send(i18n.T("en", "help")) })
    tbot.Handle("/balance", func(c tb.Context) error {
        if store != nil { _ = store.EnsureUser(context.Background(), c.Sender().ID, c.Sender().Username, "en") }
        lang := getUserLang(c)
        cr := 0
        if store != nil { if n, err := store.GetCredits(context.Background(), c.Sender().ID); err == nil { cr = n } }
        return c.Send(strings.ReplaceAll(i18n.T(lang, "balance"), "{n}", fmt.Sprintf("%d", cr)))
    })

    // Admin command: /admin grant <uid> <n> | /admin whitelist add/remove <uid>
    tbot.Handle("/admin", func(c tb.Context) error {
        if !isAdmin(c.Sender().ID) { return c.Send(i18n.T(getUserLang(c), "admin_only")) }
        parts := strings.Fields(c.Message().Text)
        if len(parts) < 2 { return c.Send("Usage: /admin grant <uid> <n> | /admin whitelist add|remove <uid>") }
        switch parts[1] {
        case "grant":
            if len(parts) < 4 { return c.Send("Usage: /admin grant <uid> <n>") }
            uid := int64(atoiSafe(parts[2]))
            n := atoiSafe(parts[3])
            if store != nil { _ = store.AddCredits(context.Background(), uid, n) }
            bal := 0
            if store != nil { if b, err := store.GetCredits(context.Background(), uid); err == nil { bal = b } }
            msg := strings.ReplaceAll(i18n.T(getUserLang(c), "granted"), "{n}", fmt.Sprintf("%d", n))
            msg = strings.ReplaceAll(msg, "{uid}", fmt.Sprintf("%d", uid))
            msg = strings.ReplaceAll(msg, "{bal}", fmt.Sprintf("%d", bal))
            return c.Send(msg)
        case "whitelist":
            if len(parts) < 4 { return c.Send("Usage: /admin whitelist add|remove <uid>") }
            action := parts[2]
            uid := int64(atoiSafe(parts[3]))
            switch action {
            case "add":
                if store != nil { _ = store.SetWhitelist(context.Background(), uid, true) }
                return c.Send(strings.ReplaceAll(i18n.T(getUserLang(c), "free_added"), "{uid}", fmt.Sprintf("%d", uid)))
            case "remove":
                if store != nil { _ = store.SetWhitelist(context.Background(), uid, false) }
                return c.Send(strings.ReplaceAll(i18n.T(getUserLang(c), "free_removed"), "{uid}", fmt.Sprintf("%d", uid)))
            default:
                return c.Send("Usage: /admin whitelist add|remove <uid>")
            }
        default:
            return c.Send("Usage: /admin grant <uid> <n> | /admin whitelist add|remove <uid>")
        }
    })

    tbot.Handle(tb.OnText, func(c tb.Context) error {
        text := c.Text()
        if strings.HasPrefix(text, "/") { return nil }
        if store != nil { _ = store.EnsureUser(context.Background(), c.Sender().ID, c.Sender().Username, "en") }
        if !isFreeUser(c.Sender().ID) && store != nil {
            if n, err := store.GetCredits(context.Background(), c.Sender().ID); err == nil && n <= 0 {
                lang := getUserLang(c)
                return c.Send(i18n.T(lang, "credits_none"))
            }
        }
        gid := newID()
        _, err := queue.EnqueueGenerate(context.Background(), asynqClient, queue.GeneratePayload{GID: gid, ChatID: c.Chat().ID, Mode: "normal", Prompt: text})
        if err != nil { return c.Send("Error") }
        lang := getUserLang(c)
        return c.Send(i18n.T(lang, "gen"))
    })

    tbot.Handle(tb.OnPhoto, func(c tb.Context) error {
        // Resolve largest photo file_id to URL
        var fid string
        if p := c.Message().Photo; p != nil { fid = p.FileID }
        fileURL := ""
        if fid != "" {
            if u, err := images.GetFileURL(appCfg.BotToken, fid); err == nil { fileURL = u }
        }
        uid := c.Sender().ID
        // Copy Mode flow
        if copyState.IsActive(uid) {
            if !copyState.NeedSelfie(uid) {
                // Got style
                copyState.SetStyle(uid, fileURL)
                return c.Send("Style OK. Now send your selfie.")
            }
            // Got selfie
            styleURL := copyState.GetStyle(uid)
            selfieURL := fileURL
            prompt, negative, seed := "adult person, same scene as reference", "low-res, artifacts, watermark", "style-seed"
            if oa != nil {
                if p, n, s, err := oa.CraftPromptFromStyle(context.Background(), styleURL); err == nil { prompt, negative, seed = p, n, s }
            }
            gid := newID()
            _, err := queue.EnqueueGenerate(context.Background(), asynqClient, queue.GeneratePayload{GID: gid, ChatID: uid, Mode: "copy", Prompt: prompt, Negative: negative, Seed: seed, SelfieURL: selfieURL, StyleURL: styleURL})
            copyState.Clear(uid)
            if err != nil { return c.Send("Error") }
            return c.Send(i18n.T("en", "gen"))
        }
        // Default: caption prompt + selfie, else preset prompt
        prompt := c.Message().Caption
        negative := ""
        if prompt == "" {
            if presetState.Has(uid) { prompt, negative = presetState.Get(uid) }
        }
        if prompt == "" {
            return c.Send("Please add a caption (prompt) or choose Presets.")
        }
        if !isFreeUser(c.Sender().ID) && store != nil {
            if n, err := store.GetCredits(context.Background(), c.Sender().ID); err == nil && n <= 0 {
                lang := getUserLang(c)
                return c.Send(i18n.T(lang, "credits_none"))
            }
        }
        gid := newID()
        _, err := queue.EnqueueGenerate(context.Background(), asynqClient, queue.GeneratePayload{GID: gid, ChatID: c.Chat().ID, Mode: "normal", Prompt: prompt, Negative: negative, SelfieURL: fileURL})
        if err != nil { return c.Send("Error") }
        lang := getUserLang(c)
        return c.Send(i18n.T(lang, "gen"))
    })

    // Copy Mode: /copy (style → selfie)
    tbot.Handle("/copy", func(c tb.Context) error {
        ensureCopyState()
        copyState.SetAwaitStyle(c.Sender().ID)
        return c.Send("Copy Mode: send a style reference photo.")
    })

    // Language (simple): /lang en|ru|ro|de
    tbot.Handle("/lang", func(c tb.Context) error {
        parts := strings.Fields(c.Message().Text)
        if len(parts) < 2 { return c.Send(i18n.T("en", "choose_lang")+" (en/ru/ro/de)") }
        lang := strings.ToLower(parts[1])
        switch lang { case "en","ru","ro","de": default: return c.Send("Unknown lang") }
        if store != nil { _ = store.SetLang(context.Background(), c.Sender().ID, lang) }
        return c.Send("OK")
    })

    // Gallery: paginated
    tbot.Handle("/gallery", func(c tb.Context) error {
        return sendGalleryPage(c, 0)
    })
    // Callback for gallery pagination: data="gal:<page>"
    tbot.Handle(tb.OnCallback, func(c tb.Context) error {
        data := c.Callback().Data
        if strings.HasPrefix(data, "gal:") {
            pageStr := strings.TrimPrefix(data, "gal:")
            page := atoiSafe(pageStr)
            return sendGalleryPage(c, page)
        }
        if strings.HasPrefix(data, "buy:") {
            key := strings.TrimPrefix(data, "buy:")
            // find pack and send invoice
            if p := domain.FindPack(key); p != nil {
                title := "iModel Credits"
                desc := fmt.Sprintf("%d generations — %d★", p.Credits, p.Stars)
                payload := "buy:" + p.Key
                if err := payments.SendStarsInvoice(appCfg.BotToken, c.Sender().ID, title, desc, payload, p.Stars); err != nil {
                    return c.Respond(&tb.CallbackResponse{Text: "Payment init failed"})
                }
                return c.Respond()
            }
            return c.Respond(&tb.CallbackResponse{Text: "Unknown pack"})
        }
        return nil
    })

    // /buy menu
    tbot.Handle("/buy", func(c tb.Context) error {
        // Build three buttons
        btn := func(key, label string) tb.InlineButton { return tb.InlineButton{Unique: "buy_"+key, Text: label, Data: "buy:"+key} }
        b10 := btn("pack10", "10 gens — 200★")
        b30 := btn("pack30", "30 gens — 500★")
        b100 := btn("pack100", "100 gens — 1200★")
        mk := &tb.ReplyMarkup{InlineKeyboard: [][]tb.InlineButton{{b10, b30, b100}}}
        lang := getUserLang(c)
        title := i18n.T(lang, "buy_title")
        // Use localized button text
        b10 := tb.InlineButton{Unique: "buy_pack10", Text: i18n.T(lang, "buy_btn_10"), Data: "buy:pack10"}
        b30 := tb.InlineButton{Unique: "buy_pack30", Text: i18n.T(lang, "buy_btn_30"), Data: "buy:pack30"}
        b100 := tb.InlineButton{Unique: "buy_pack100", Text: i18n.T(lang, "buy_btn_100"), Data: "buy:pack100"}
        mk := &tb.ReplyMarkup{InlineKeyboard: [][]tb.InlineButton{{b10, b30, b100}}}
        return c.Send(title, mk)
    })

    // Payments: accept pre-checkout always
    tbot.Handle(tb.OnPreCheckoutQuery, func(c tb.Context) error {
        if c.PreCheckoutQuery() != nil { _ = payments.AnswerPreCheckout(appCfg.BotToken, c.PreCheckoutQuery().ID, true, "") }
        return nil
    })

    // Payments: successful
    tbot.Handle(tb.OnSuccessfulPayment, func(c tb.Context) error {
        sp := c.Message().SuccessfulPayment
        if sp == nil { return nil }
        payload := sp.InvoicePayload
        if strings.HasPrefix(payload, "buy:") {
            key := strings.TrimPrefix(payload, "buy:")
            if p := domain.FindPack(key); p != nil && store != nil {
                _ = store.AddCredits(context.Background(), c.Sender().ID, p.Credits)
                bal := 0
                if n, err := store.GetCredits(context.Background(), c.Sender().ID); err == nil { bal = n }
                lang := getUserLang(c)
                msg := strings.ReplaceAll(i18n.T(lang, "bought"), "{add}", fmt.Sprintf("%d", p.Credits))
                msg = strings.ReplaceAll(msg, "{all}", fmt.Sprintf("%d", bal))
                return c.Send(msg)
            }
        }
        return nil
    })

    // Presets: inline keyboard with callbacks
    tbot.Handle("/presets", func(c tb.Context) error {
        var rows [][]tb.InlineButton
        row := []tb.InlineButton{}
        for i, p := range domain.Presets {
            btn := tb.InlineButton{Unique: "preset_"+p.Key, Text: p.Label, Data: p.Key}
            row = append(row, btn)
            if (i+1)%3 == 0 { rows = append(rows, row); row = []tb.InlineButton{} }
        }
        if len(row) > 0 { rows = append(rows, row) }
        markup := &tb.ReplyMarkup{InlineKeyboard: rows}
        return c.Send("Choose a preset, then send a selfie.", markup)
    })
    // Register callbacks for each preset key
    for _, p := range domain.Presets {
        preset := p
        tbot.Handle(&tb.InlineButton{Unique: "preset_"+preset.Key}, func(c tb.Context) error {
            ensurePresetState()
            presetState.Set(c.Sender().ID, preset.Prompt, preset.Negative)
            return c.Respond(&tb.CallbackResponse{Text: "Preset selected. Now send a selfie."})
        })
    }

    // Promo code: /promo CODE
    tbot.Handle("/promo", func(c tb.Context) error {
        parts := strings.Fields(c.Message().Text)
        if len(parts) < 2 { return c.Send("Usage: /promo CODE") }
        code := strings.ToUpper(parts[1])
        add, ok := domain.PromoCredits[code]
        if !ok { return c.Send(i18n.T("en", "promo_bad")) }
        if store != nil { _ = store.AddCredits(context.Background(), c.Sender().ID, add) }
        msg := strings.ReplaceAll(i18n.T("en", "promo_ok"), "{add}", fmt.Sprintf("%d", add))
        // fetch new balance
        bal := 0
        if store != nil { if n, err := store.GetCredits(context.Background(), c.Sender().ID); err == nil { bal = n } }
        msg = strings.ReplaceAll(msg, "{all}", fmt.Sprintf("%d", bal))
        return c.Send(msg)
    })

    // Referral link: /refer
    tbot.Handle("/refer", func(c tb.Context) error {
        uname := ""
        if tbot != nil && tbot.Me != nil { uname = tbot.Me.Username }
        if uname == "" { return c.Send("Unable to detect bot username.") }
        link := fmt.Sprintf("https://t.me/%s?start=ref_%d", uname, c.Sender().ID)
        return c.Send("Invite a friend: " + link)
    })
}

// ProcessWebhook feeds an incoming update JSON to telebot router.
func ProcessWebhook(body []byte) error {
    if tbot == nil { return nil }
    var upd tb.Update
    if err := json.Unmarshal(body, &upd); err != nil { return err }
    tbot.ProcessUpdate(upd)
    return nil
}

func sendGalleryPage(c tb.Context, page int) error {
    const pageSize = 3
    if store == nil { return c.Send("Gallery empty") }
    uid := c.Sender().ID
    total, err := store.CountUserGenerationsFinal(context.Background(), uid)
    if err != nil || total == 0 { return c.Send(i18n.T("en", "gallery_empty")) }
    maxPage := (total + pageSize - 1) / pageSize
    if page < 0 { page = 0 }
    if page >= maxPage { page = maxPage - 1 }
    offset := page * pageSize
    arr, err := store.ListUserGenerationsFinalPaged(context.Background(), uid, offset, pageSize)
    if err != nil || len(arr) == 0 { return c.Send(i18n.T("en", "gallery_empty")) }
    for _, u := range arr {
        _ = c.Send(&tb.Photo{File: tb.FromURL(u)})
    }
    // pager buttons
    prev := tb.InlineButton{Unique: "gal_prev", Text: "⬅️ Prev", Data: fmt.Sprintf("gal:%d", page-1)}
    next := tb.InlineButton{Unique: "gal_next", Text: "Next ➡️", Data: fmt.Sprintf("gal:%d", page+1)}
    row := []tb.InlineButton{}
    if page > 0 { row = append(row, prev) }
    if page < maxPage-1 { row = append(row, next) }
    if len(row) > 0 { _ = c.Send(fmt.Sprintf("Page %d/%d", page+1, maxPage), &tb.ReplyMarkup{InlineKeyboard: [][]tb.InlineButton{row}}) }
    return nil
}

// simple in-memory copy state (dev)
type copySession struct { style string; awaitingSelfie bool }
type copyStore struct { m map[int64]*copySession }
var copyState = &copyStore{m: map[int64]*copySession{}}
func ensureCopyState() {}
func (s *copyStore) SetAwaitStyle(uid int64){ s.m[uid] = &copySession{style:"", awaitingSelfie:false} }
func (s *copyStore) IsActive(uid int64) bool { _, ok := s.m[uid]; return ok }
func (s *copyStore) NeedSelfie(uid int64) bool { cs, ok := s.m[uid]; return ok && cs.awaitingSelfie }
func (s *copyStore) SetStyle(uid int64, u string){ if cs, ok := s.m[uid]; ok { cs.style=u; cs.awaitingSelfie=true } }
func (s *copyStore) GetStyle(uid int64) string { if cs, ok := s.m[uid]; ok { return cs.style }; return "" }
func (s *copyStore) Clear(uid int64){ delete(s.m, uid) }

// in-memory preset state: prompt + negative per user
type presetSess struct{ prompt, negative string }
type presetStore struct{ m map[int64]presetSess }
var presetState = &presetStore{m: map[int64]presetSess{}}
func ensurePresetState(){}
func (s *presetStore) Set(uid int64, p, n string){ s.m[uid] = presetSess{prompt:p, negative:n} }
func (s *presetStore) Has(uid int64) bool { _, ok := s.m[uid]; return ok }
func (s *presetStore) Get(uid int64) (string,string){ v := s.m[uid]; return v.prompt, v.negative }

// helpers
func atoiSafe(s string) int { n, _ := strconv.Atoi(s); return n }
func getUserLang(c tb.Context) string {
    if store == nil { return "en" }
    if lang, err := store.GetLang(context.Background(), c.Sender().ID); err == nil && lang != "" { return lang }
    return "en"
}
func isFreeUser(uid int64) bool {
    if appCfg.AdminIDs != nil && appCfg.AdminIDs[uid] { return true }
    if appCfg.WhitelistIDs != nil && appCfg.WhitelistIDs[uid] { return true }
    return false
}
func isAdmin(uid int64) bool { return appCfg.AdminIDs != nil && appCfg.AdminIDs[uid] }
