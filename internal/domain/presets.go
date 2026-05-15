package domain

type Preset struct{ Key, Label string; Prompt string; Negative string }

const baseNegative = "deformed face, disfigured, mutated hands, extra fingers, bad anatomy, ugly, blurry, out of focus, overexposed, underexposed, cartoon, painting, illustration, cgi, 3d render, anime, noise, grain, jpeg artifacts, chromatic aberration, low-res, watermark, text, logo, duplicate, cloned face"

var Presets = []Preset{
    {
        Key:      "studio_soft",
        Label:    "📸 Studio",
        Prompt:   "professional studio portrait of a real person, soft beauty dish lighting, dark seamless backdrop, 85mm f/1.4 lens, shallow depth of field, sharp eyes, skin texture visible, editorial fashion magazine quality, 8K",
        Negative: baseNegative,
    },
    {
        Key:      "sunset_outdoor",
        Label:    "🌇 Sunset",
        Prompt:   "outdoor portrait at golden hour sunset, warm rim lighting, bokeh background, 85mm f/1.8, skin luminosity, natural hair, photo-realistic, lifestyle magazine",
        Negative: baseNegative,
    },
    {
        Key:      "coffee_shop",
        Label:    "☕ Cafe",
        Prompt:   "candid cafe portrait, warm tungsten ambient light, shallow depth of field, film grain, cozy interior bokeh, natural expression, 35mm f/2.0, lifestyle photography",
        Negative: baseNegative,
    },
    {
        Key:      "forest_film",
        Label:    "🌲 Forest",
        Prompt:   "forest portrait, soft diffused natural light through canopy, misty atmospheric background, 50mm f/1.8, film emulation, earthy tones, outdoor editorial",
        Negative: baseNegative,
    },
    {
        Key:      "bw_classic",
        Label:    "⚫⚪ B&W",
        Prompt:   "black and white studio portrait, dramatic Rembrandt lighting, deep shadows, sharp facial detail, high contrast, 85mm, fine art photography, silver gelatin look",
        Negative: "color, tinted, sepia, " + baseNegative,
    },
    {
        Key:      "street_cinema",
        Label:    "🎬 Street",
        Prompt:   "cinematic street portrait at night, neon light bokeh, 35mm anamorphic lens, moody color grading, film noir atmosphere, rain-slicked pavement reflections, cinematic 2.39:1",
        Negative: baseNegative,
    },
    {
        Key:      "luxury_fashion",
        Label:    "💎 Fashion",
        Prompt:   "high fashion editorial portrait, glossy magazine cover, dramatic studio lighting, Versace aesthetic, sharp eyes, flawless skin, 120mm telephoto, ultra-sharp, 8K",
        Negative: baseNegative,
    },
    {
        Key:      "vintage_film",
        Label:    "🎞 Vintage",
        Prompt:   "1970s film portrait, Kodak Portra 400 grain, warm faded tones, natural window light, vintage aesthetic, slightly overexposed, analog photography",
        Negative: "digital, cgi, sharp, oversharpened, neon, " + baseNegative,
    },
    {
        Key:      "tech_corporate",
        Label:    "💼 Corporate",
        Prompt:   "professional LinkedIn headshot, clean office background, neutral soft-box lighting, business attire, confident expression, 85mm f/2.0, crisp and polished",
        Negative: baseNegative,
    },
    {
        Key:      "dramatic_dark",
        Label:    "🌑 Dark",
        Prompt:   "dramatic portrait, single hard key light, deep shadows, dark seamless background, chiaroscuro lighting, cinematic color grade, 85mm f/1.2, intense gaze",
        Negative: baseNegative,
    },
}

func FindPreset(key string) *Preset {
    for i := range Presets { if Presets[i].Key == key { return &Presets[i] } }
    return nil
}
