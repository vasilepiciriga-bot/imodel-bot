import { useEffect, useState } from "react";
import { Link, Route, Routes, useSearchParams } from "react-router-dom";
import { createSession, fetchMe, setToken } from "./lib/api";
import { Home } from "./pages/Home";
import { Create } from "./pages/Create";
import { TrendLab } from "./pages/TrendLab";
import { Gallery } from "./pages/Gallery";
import { Pricing } from "./pages/Pricing";
import { LoadingStudio } from "./components/LoadingStudio";

function Photoshoots() {
  return (
    <section>
      <h2 className="text-xl font-semibold mb-2">Photoshoots</h2>
      <Link to="/trends" className="text-studio-mint">
        Browse catalog →
      </Link>
    </section>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [credits, setCredits] = useState(0);
  const [params] = useSearchParams();

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();
    (async () => {
      try {
        const s = await createSession();
        setToken(s.token);
        const me = await fetchMe();
        setCredits(me.credits);
      } catch {
        setCredits(0);
      }
      setReady(true);
    })();
  }, []);

  if (!ready) return <LoadingStudio label="Opening studio…" />;

  const styleKey = params.get("style") || undefined;

  return (
    <div className="mx-auto max-w-lg p-4 pb-10">
      <nav className="mb-4 flex gap-2 text-xs text-white/50">
        <Link to="/">Home</Link>
        <Link to="/create">Create</Link>
        <Link to="/gallery">Gallery</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Home credits={credits} />} />
        <Route path="/create" element={<Create styleKey={styleKey} />} />
        <Route path="/photoshoots" element={<Photoshoots />} />
        <Route path="/trends" element={<TrendLab />} />
        <Route path="/gallery" element={<Gallery />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/profile" element={<p className="text-white/60">Profile — credits: {credits}</p>} />
        <Route path="/settings" element={<p className="text-white/60">Settings — use /forget in bot for full delete.</p>} />
      </Routes>
    </div>
  );
}
