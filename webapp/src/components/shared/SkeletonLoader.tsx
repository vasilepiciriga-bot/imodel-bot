function Shimmer({ className }: { className: string }) {
  return (
    <div className={`relative overflow-hidden bg-[#E8E8ED] rounded-[12px] ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.6s_infinite]
        bg-gradient-to-r from-transparent via-white/60 to-transparent" />
    </div>
  )
}

export function PresetSkeleton() {
  return (
    <div className="rounded-[18px] overflow-hidden">
      <Shimmer className="aspect-[3/4] rounded-[18px]" />
      <div className="mt-2 space-y-1.5 px-1">
        <Shimmer className="h-3.5 w-3/4" />
        <Shimmer className="h-3 w-1/2" />
      </div>
    </div>
  )
}

export function GallerySkeleton() {
  return (
    <div className="relative overflow-hidden bg-[#E8E8ED] rounded-[14px] w-full" style={{ aspectRatio: '1 / 1.4' }}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.6s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent" />
    </div>
  )
}

export function StatSkeleton() {
  return (
    <div className="rounded-[16px] bg-[#F5F5F7] p-4 space-y-2">
      <Shimmer className="h-3 w-2/3" />
      <Shimmer className="h-7 w-1/2" />
    </div>
  )
}

export function CardSkeleton({ lines = 2 }: { lines?: number }) {
  return (
    <div className="rounded-[16px] bg-white border border-black/[0.05] p-4 space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Shimmer key={i} className={`h-3.5 ${i === 0 ? 'w-4/5' : 'w-3/5'}`} />
      ))}
    </div>
  )
}
