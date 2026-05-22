export function LoadingStudio({ label = "Crafting your photoshoot…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-studio-mint">
      <div className="h-10 w-10 animate-pulse rounded-full border-2 border-studio-mint/40 border-t-studio-mint" />
      <p className="text-sm text-white/70">{label}</p>
    </div>
  );
}
