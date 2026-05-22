import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchTrending } from "../lib/api";

export function TrendLab() {
  const [items, setItems] = useState<Array<{ key: string; name: string }>>([]);

  useEffect(() => {
    fetchTrending().then((d) => setItems(d.items || [])).catch(() => setItems([]));
  }, []);

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Trend Lab</h2>
      <p className="text-sm text-white/60">Trending looks this week.</p>
      <ul className="space-y-2">
        {items.map((s) => (
          <li key={s.key}>
            <Link to={`/create?style=${s.key}`} className="block rounded-lg border border-white/10 px-3 py-2">
              {s.name}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
