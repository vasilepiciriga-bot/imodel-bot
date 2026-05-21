import { useCallback, useEffect, useMemo, useState } from "react";

type Screen = "home" | "create" | "photoshoots" | "trendlab" | "gallery" | "pricing" | "profile" | "referrals" | "result";

type Style = {
  key: string;
  name: string;
  category: string;
  price_credits?: number;
  is_trending?: boolean;
  commercial_angle?: string;
};

type Me = { credits: number; role: string; chat_id: number };
type Pkg = { payload: string; title: string; stars: number; credits: number; description?: string };

const LOADING_STEPS = [
  "Reading your selfie",
  "Locking your identity",
  "Designing the lighting",
  "Styling the scene",
  "Creating your premium photos",
  "Final polish",
];

declare global {
  interface Window {
    Telegram?: { WebApp?: { ready: () => void; expand: () => void; initData: string; openInvoice?: (url: string) => void } };
  }
}

function Nav({ screen, setScreen }: { screen: Screen; setScreen: (s: Screen) => void }) {
  const items: { id: Screen; label: string }[] = [
    { id: "home", label: "Home" },
    { id: "photoshoots", label: "Shoots" },
    { id: "trendlab", label: "Trends" },
    { id: "gallery", label: "Gallery" },
    { id: "pricing", label: "Buy" },
  ];
  return (
    <nav className="fixed bottom-0 left-0 right-0 glass flex justify-around py-2 px-1 z-20">
      {items.map((i) => (
        <button
          key={i.id}
          type="button"
          onClick={() => setScreen(i.id)}
          className={`text-xs px-2 py-1 rounded-lg ${screen === i.id ? "text-accent bg-white/10" : "text-muted"}`}
        >
          {i.label}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const tg = window.Telegram?.WebApp;
  const [screen, setScreen] = useState<Screen>("home");
  const [token, setToken] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [styles, setStyles] = useState<Style[]>([]);
  const [trending, setTrending] = useState<Style[]>([]);
  const [weekly, setWeekly] = useState<Style[]>([]);
  const [packages, setPackages] = useState<Pkg[]>([]);
  const [gallery, setGallery] = useState<{ output_url?: string; result_id?: string; style_key?: string }[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<Style | null>(null);
  const [selfie, setSelfie] = useState<File | null>(null);
  const [reference, setReference] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("Preparing your studio…");
  const [loadingStep, setLoadingStep] = useState(0);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const api = useCallback(
    async (path: string, opts: RequestInit = {}) => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(opts.headers as Record<string, string>),
      };
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(path, { ...opts, headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    },
    [token]
  );

  const refreshMe = useCallback(async () => {
    if (!token) return;
    const data = await api("/api/v1/me");
    setMe(data);
  }, [api, token]);

  useEffect(() => {
    tg?.ready();
    tg?.expand();
    (async () => {
      try {
        const sess = await fetch("/api/v1/webapp/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ initData: tg?.initData || "" }),
        });
        const sd = await sess.json();
        if (!sess.ok) {
          setError("Open inside Telegram to sign in.");
          return;
        }
        setToken(sd.token);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [tg]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        await refreshMe();
        const s = await api("/api/v1/styles");
        setStyles(s.items || []);
        const tr = await api("/api/v1/styles/trending");
        setTrending(tr.items || []);
        const wk = await api("/api/v1/trends/weekly");
        setWeekly(wk.items || []);
        const pk = await api("/api/v1/packages");
        setPackages(pk.packages || []);
        const gal = await api("/api/v1/gallery");
        setGallery(gal.items || []);
      } catch (e) {
        console.warn(e);
      }
    })();
  }, [token, api, refreshMe]);

  const fileToB64 = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(String(fr.result));
      fr.onerror = reject;
      fr.readAsDataURL(file);
    });

  const pollJob = async (jobId: string) => {
    for (let i = 0; i < 80; i++) {
      setLoadingStep(Math.min(LOADING_STEPS.length - 1, Math.floor(i / 12)));
      setStatus(LOADING_STEPS[Math.min(LOADING_STEPS.length - 1, Math.floor(i / 12))]);
      const data = await api(`/api/v1/generations/${jobId}`);
      if (data.status === "ready" && data.output_url) {
        setResultUrl(data.output_url);
        setScreen("result");
        await refreshMe();
        const gal = await api("/api/v1/gallery");
        setGallery(gal.items || []);
        return;
      }
      if (data.status === "failed") throw new Error(data.error || "Generation failed");
      await new Promise((r) => setTimeout(r, 2500));
    }
    throw new Error("Timed out — check Gallery soon");
  };

  const generate = async () => {
    if (!selfie) {
      setError("Upload a selfie first");
      return;
    }
    if (!selectedStyle && !prompt.trim()) {
      setError("Pick a photoshoot or describe your scene");
      return;
    }
    setError(null);
    setStatus(LOADING_STEPS[0]);
    setLoadingStep(0);
    try {
      if (selectedStyle) {
        await api("/api/v1/events/style", {
          method: "POST",
          body: JSON.stringify({ style_key: selectedStyle.key, event: "generate" }),
        });
      }
      const body: Record<string, string> = {
        image_b64: await fileToB64(selfie),
        prompt: prompt.trim(),
      };
      if (selectedStyle) body.style_key = selectedStyle.key;
      if (reference) body.reference_b64 = await fileToB64(reference);
      const created = await api("/api/v1/generations", { method: "POST", body: JSON.stringify(body) });
      await pollJob(created.job_id);
    } catch (e) {
      setError(String(e));
      setStatus("Something went wrong");
    }
  };

  const businessStyles = useMemo(() => styles.filter((s) => s.category === "Business").slice(0, 4), [styles]);
  const datingStyles = useMemo(() => styles.filter((s) => s.category === "Dating").slice(0, 3), [styles]);
  const luxuryStyles = useMemo(() => styles.filter((s) => s.category === "Luxury").slice(0, 4), [styles]);

  const pickStyle = (s: Style) => {
    setSelectedStyle(s);
    setScreen("create");
    api("/api/v1/events/style", {
      method: "POST",
      body: JSON.stringify({ style_key: s.key, event: "select" }),
    }).catch(() => {});
  };

  return (
    <div className="max-w-lg mx-auto px-4 pb-24 pt-4">
      <header className="flex items-center justify-between mb-6">
        <div className="font-bold text-lg tracking-wide">iModel Studio</div>
        <div className="glass text-xs px-3 py-1 rounded-full text-muted">
          credits: <span className="text-accent font-semibold">{me?.credits ?? "—"}</span>
        </div>
      </header>

      {error && (
        <div className="mb-4 p-3 rounded-xl border border-danger/40 bg-danger/10 text-sm text-danger">{error}</div>
      )}

      {screen === "home" && (
        <>
          <section className="mb-8">
            <h1 className="text-3xl font-semibold leading-tight mb-2">Your AI photo studio inside Telegram</h1>
            <p className="text-muted text-sm">Premium portraits without a photographer. Pick a trending look, upload a selfie, receive studio-grade photos.</p>
            <button type="button" className="mt-4 w-full py-3 rounded-xl bg-gradient-to-r from-accent to-electric text-bg font-bold" onClick={() => setScreen("photoshoots")}>
              Open Studio
            </button>
          </section>
          <Section title="Trending Now" items={trending.slice(0, 6)} onPick={pickStyle} />
          <Section title="Popular for Business" items={businessStyles} onPick={pickStyle} />
          <Section title="Dating Upgrade" items={datingStyles} onPick={pickStyle} />
          <Section title="Luxury Status" items={luxuryStyles} onPick={pickStyle} />
          <button type="button" className="w-full glass rounded-xl p-4 text-left mb-4" onClick={() => { setSelectedStyle(styles.find((s) => s.key === "copy_any_style") || null); setScreen("create"); }}>
            <div className="text-gold font-semibold">Copy Any Style</div>
            <div className="text-muted text-sm">Upload a reference + your selfie — recreate the scene with your face</div>
          </button>
          {resultUrl && (
            <div className="glass rounded-xl p-3 mb-4">
              <div className="text-sm text-muted mb-2">Latest result</div>
              <img src={resultUrl} alt="result" className="rounded-lg w-full" />
            </div>
          )}
        </>
      )}

      {screen === "photoshoots" && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Photoshoots</h2>
          <div className="grid gap-3">
            {styles.map((s) => (
              <button key={s.key} type="button" className="glass rounded-xl p-4 text-left" onClick={() => pickStyle(s)}>
                <div className="flex justify-between">
                  <span className="font-medium">{s.name}</span>
                  <span className="text-accent text-sm">{s.price_credits ?? 1} cr</span>
                </div>
                <div className="text-muted text-xs mt-1">{s.category}{s.is_trending ? " · Trending" : ""}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {screen === "trendlab" && (
        <div>
          <h2 className="text-xl font-semibold mb-2">Trend Lab</h2>
          <p className="text-muted text-sm mb-4">Weekly featured looks — updated by the studio team.</p>
          <Section title="This week" items={weekly.length ? weekly : trending} onPick={pickStyle} />
        </div>
      )}

      {screen === "create" && (
        <div>
          <h2 className="text-xl font-semibold mb-2">Create</h2>
          {selectedStyle && (
            <div className="glass rounded-xl p-3 mb-4 text-sm">
              <span className="text-gold">{selectedStyle.name}</span>
              <span className="text-muted"> · {selectedStyle.price_credits ?? 1} credits</span>
            </div>
          )}
          <label className="block text-sm text-soft mb-2">Selfie</label>
          <input type="file" accept="image/*" className="w-full mb-4 text-sm" onChange={(e) => setSelfie(e.target.files?.[0] || null)} />
          {(selectedStyle?.key === "copy_any_style" || reference) && (
            <>
              <label className="block text-sm text-soft mb-2">Reference photo (style to copy)</label>
              <input type="file" accept="image/*" className="w-full mb-4 text-sm" onChange={(e) => setReference(e.target.files?.[0] || null)} />
            </>
          )}
          <label className="block text-sm text-soft mb-2">Extra scene notes (optional)</label>
          <textarea className="w-full rounded-xl bg-surface border border-white/10 p-3 text-sm mb-4 min-h-[80px]" value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Optional mood or details…" />
          <div className="glass rounded-xl p-4 mb-4 text-sm text-soft">{status}</div>
          <button type="button" className="w-full py-3 rounded-xl bg-accent text-bg font-bold" onClick={generate}>
            Create photoshoot
          </button>
        </div>
      )}

      {screen === "gallery" && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Gallery</h2>
          {gallery.length === 0 && <p className="text-muted text-sm">No results yet. Create your first look.</p>}
          <div className="grid gap-3">
            {gallery.map((g, i) => (
              <div key={g.result_id || g.output_url || i} className="glass rounded-xl overflow-hidden">
                {g.output_url && <img src={g.output_url} alt="" className="w-full" />}
                <div className="p-2 text-xs text-muted flex justify-between">
                  <span>{g.style_key || "custom"}</span>
                  {g.output_url && (
                    <a href={g.output_url} target="_blank" rel="noreferrer" className="text-accent">
                      Download
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {screen === "pricing" && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Pricing</h2>
          <p className="text-muted text-sm mb-4">Pay with Telegram Stars. Credits are used per successful photoshoot.</p>
          {packages.map((p) => (
            <div key={p.payload} className="glass rounded-xl p-4 mb-3">
              <div className="font-semibold">{p.title}</div>
              <div className="text-sm text-muted">{p.description || `${p.credits} premium photos`}</div>
              <div className="mt-2 text-accent">{p.stars} Stars · {p.credits} credits</div>
              <p className="text-xs text-muted mt-2">Purchase via bot /buy — Stars checkout opens in chat.</p>
            </div>
          ))}
        </div>
      )}

      {screen === "profile" && (
        <div className="glass rounded-xl p-4">
          <h2 className="text-xl font-semibold mb-4">Profile</h2>
          <p>Role: {me?.role}</p>
          <p>Credits: {me?.credits}</p>
        </div>
      )}

      {screen === "referrals" && (
        <div className="glass rounded-xl p-4">
          <h2 className="text-xl font-semibold mb-2">Referrals</h2>
          <p className="text-sm text-muted">Invite friends from the bot with /refer — you both earn bonus credits.</p>
        </div>
      )}

      {screen === "result" && resultUrl && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Your photoshoot</h2>
          <img src={resultUrl} alt="Your result" className="rounded-xl w-full mb-4" />
          <button type="button" className="w-full py-3 rounded-xl glass mb-2" onClick={() => setScreen("photoshoots")}>
            Try another look
          </button>
          <button type="button" className="w-full py-3 rounded-xl bg-gold/20 text-gold" onClick={() => setScreen("pricing")}>
            Get more credits
          </button>
        </div>
      )}

      <Nav screen={screen} setScreen={setScreen} />
    </div>
  );
}

function Section({ title, items, onPick }: { title: string; items: Style[]; onPick: (s: Style) => void }) {
  if (!items.length) return null;
  return (
    <section className="mb-6">
      <h3 className="text-sm text-muted uppercase tracking-wider mb-3">{title}</h3>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {items.map((s) => (
          <button key={s.key} type="button" className="glass rounded-xl p-3 min-w-[140px] text-left shrink-0" onClick={() => onPick(s)}>
            <div className="font-medium text-sm">{s.name}</div>
            <div className="text-xs text-muted mt-1">{s.category}</div>
          </button>
        ))}
      </div>
    </section>
  );
}
