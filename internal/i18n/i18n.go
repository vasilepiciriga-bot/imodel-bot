package i18n

import (
	"embed"
	"encoding/json"
)

//go:embed *.json
var fs embed.FS

var msgs map[string]map[string]string

func init() {
	msgs = map[string]map[string]string{}
	for _, lang := range []string{"ru","en","ro","de"} {
		b, err := fs.ReadFile(lang + ".json")
		if err != nil { continue }
		var m map[string]string
		_ = json.Unmarshal(b, &m)
		msgs[lang] = m
	}
}

func T(lang, key string) string {
	if m, ok := msgs[lang]; ok {
		if v, ok := m[key]; ok { return v }
	}
	if m, ok := msgs["en"]; ok {
		if v, ok := m[key]; ok { return v }
	}
	return key
}
