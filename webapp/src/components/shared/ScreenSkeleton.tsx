export function ScreenSkeleton() {
  return (
    <div className="flex-1 p-4 space-y-4 animate-pulse">
      <div className="h-8 bg-gray-200 rounded-card w-2/3" />
      <div className="h-48 bg-gray-200 rounded-card" />
      <div className="h-12 bg-gray-200 rounded-card" />
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="aspect-square bg-gray-200 rounded-card" />
        ))}
      </div>
    </div>
  )
}
