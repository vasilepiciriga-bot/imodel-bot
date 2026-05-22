import { Link } from "react-router-dom";

export function Home({ credits }: { credits: number }) {
  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight">iModel Studio</h1>
      <p className="text-white/60">Premium AI photoshoots — pick a look, upload a selfie, receive polished portraits.</p>
      <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm">Credits: {credits}</div>
      <div className="grid gap-2">
        <Link to="/create" className="rounded-lg bg-studio-mint px-4 py-3 text-center font-semibold text-black">
          Start photoshoot
        </Link>
        <Link to="/photoshoots" className="rounded-lg border border-white/15 px-4 py-3 text-center">
          Photoshoots
        </Link>
        <Link to="/trends" className="rounded-lg border border-white/15 px-4 py-3 text-center">
          Trend Lab
        </Link>
        <Link to="/gallery" className="rounded-lg border border-white/15 px-4 py-3 text-center">
          Gallery
        </Link>
        <Link to="/pricing" className="rounded-lg border border-white/15 px-4 py-3 text-center">
          Pricing
        </Link>
      </div>
    </section>
  );
}
