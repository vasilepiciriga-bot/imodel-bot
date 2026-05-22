import { useEffect, useState } from "react";
import { fetchGallery } from "../lib/api";
import { LoadingStudio } from "../components/LoadingStudio";

export function Gallery() {
  const [items, setItems] = useState<Array<{ image_url?: string; job_id?: string }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGallery()
      .then((d) => setItems((d.items as typeof items) || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingStudio label="Loading your gallery…" />;

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Gallery</h2>
      <div className="grid grid-cols-2 gap-2">
        {items.map((it, i) => (
          <div key={i} className="rounded-lg border border-white/10 overflow-hidden">
            {it.image_url ? <img src={it.image_url} alt="" className="w-full" /> : <div className="p-4 text-xs">{it.job_id}</div>}
          </div>
        ))}
      </div>
      {!items.length && <p className="text-white/50">No photos yet — start a photoshoot.</p>}
    </section>
  );
}
