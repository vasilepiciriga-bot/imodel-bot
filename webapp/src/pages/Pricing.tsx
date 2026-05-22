import { useEffect, useState } from "react";
import { fetchPackages } from "../lib/api";

export function Pricing() {
  const [items, setItems] = useState<Array<{ title?: string; stars?: number; credits?: number }>>([]);

  useEffect(() => {
    fetchPackages().then((d) => setItems((d.items as typeof items) || [])).catch(() => {});
  }, []);

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Pricing</h2>
      <p className="text-sm text-white/60">Buy with Telegram Stars in the bot — open Buy from the menu.</p>
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li key={i} className="rounded-lg border border-white/10 px-3 py-2">
            <b>{p.title}</b> — {p.stars}★ · {p.credits} photos
          </li>
        ))}
      </ul>
    </section>
  );
}
