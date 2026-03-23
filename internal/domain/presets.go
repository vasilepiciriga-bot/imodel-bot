package domain

type Preset struct{ Key, Label string; Prompt string; Negative string }

var Presets = []Preset{
    {Key: "studio_soft", Label: "📸 Studio", Prompt: "studio portrait photo of an adult person, soft beauty light, dark seamless backdrop, 85mm lens, f/1.8, editorial look", Negative: "low-res, artifacts, watermark, text, logo"},
    {Key: "sunset_outdoor", Label: "🌇 Sunset", Prompt: "outdoor portrait at sunset golden hour, shallow depth of field, warm rim light, 85mm", Negative: "low-res, artifacts, watermark, text, logo"},
    {Key: "coffee_shop", Label: "☕ Cafe", Prompt: "indoor cafe portrait, warm tungsten lights, candid pose, film-like grain", Negative: "low-res, artifacts, watermark, text, logo"},
    {Key: "forest_film", Label: "🌲 Forest", Prompt: "forest portrait, diffused light, misty background, film look, 50mm", Negative: "low-res, artifacts, watermark, text, logo"},
    {Key: "bw_classic", Label: "⚫⚪ B&W", Prompt: "black and white studio portrait, dramatic Rembrandt light, high contrast, 85mm", Negative: "color, low-res, artifacts, watermark, text, logo"},
    {Key: "street_cinema", Label: "🎬 Street", Prompt: "cinematic street portrait at night, neon bokeh, 35mm, moody", Negative: "low-res, artifacts, watermark, text, logo"},
}

func FindPreset(key string) *Preset {
    for i := range Presets { if Presets[i].Key == key { return &Presets[i] } }
    return nil
}
