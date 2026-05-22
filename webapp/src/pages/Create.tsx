import { useState } from "react";
import { createGeneration, pollJob } from "../lib/api";
import { LoadingStudio } from "../components/LoadingStudio";

export function Create({ styleKey }: { styleKey?: string }) {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("Ready.");
  const [busy, setBusy] = useState(false);

  async function onGenerate(file: File | null) {
    if (!file || !prompt.trim()) {
      setStatus("Add a selfie and scene description.");
      return;
    }
    setBusy(true);
    setStatus("Preparing your photoshoot…");
    const b64 = await new Promise<string>((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result));
      r.onerror = reject;
      r.readAsDataURL(file);
    });
    try {
      const { job_id } = await createGeneration(prompt, b64, styleKey);
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const j = await pollJob(job_id);
        if (j.status === "ready" && j.output_url) {
          setStatus("Done! Open Gallery or check the bot chat.");
          setBusy(false);
          return;
        }
        if (j.status === "failed") {
          setStatus("Photoshoot could not finish. Try another look.");
          setBusy(false);
          return;
        }
      }
      setStatus("Still working — check back in Gallery shortly.");
    } catch {
      setStatus("Could not start photoshoot. Check credits and try again.");
    }
    setBusy(false);
  }

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Create</h2>
      {styleKey && <p className="text-sm text-studio-gold">Style: {styleKey}</p>}
      <input type="file" accept="image/*" onChange={(e) => onGenerate(e.target.files?.[0] || null)} />
      <textarea
        className="w-full rounded-lg border border-white/10 bg-black/30 p-3"
        rows={4}
        placeholder="Describe the scene…"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      {busy ? <LoadingStudio /> : <p className="text-sm text-white/70">{status}</p>}
    </section>
  );
}
