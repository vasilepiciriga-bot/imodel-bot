import { useRef, useState, useCallback } from 'react'
import { motion } from 'framer-motion'

interface Props {
  before: string
  after: string
}

export function BeforeAfterSlider({ before, after }: Props) {
  const [pos, setPos] = useState(50)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  const updatePos = useCallback((clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    const pct = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100))
    setPos(pct)
  }, [])

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true
    containerRef.current?.setPointerCapture(e.pointerId)
    updatePos(e.clientX)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (dragging.current) updatePos(e.clientX)
  }
  const onPointerUp = () => { dragging.current = false }

  return (
    <div
      ref={containerRef}
      className="relative rounded-card overflow-hidden select-none cursor-col-resize"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <img src={after} alt="after" className="w-full h-full object-cover" draggable={false} />

      <div className="absolute inset-0 overflow-hidden" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
        <img src={before} alt="before" className="w-full h-full object-cover" draggable={false} />
      </div>

      {/* divider line */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg"
        style={{ left: `${pos}%`, transform: 'translateX(-50%)' }}
      >
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-9 h-9 rounded-full bg-white shadow-lg flex items-center justify-center"
          whileTap={{ scale: 0.9 }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M5 8L2 5L2 11L5 8Z" fill="#6C47FF" />
            <path d="M11 8L14 5L14 11L11 8Z" fill="#6C47FF" />
          </svg>
        </motion.div>
      </div>

      <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/50 rounded-full text-white text-[10px] font-semibold">
        BEFORE
      </div>
      <div className="absolute top-2 right-2 px-2 py-0.5 bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] rounded-full text-white text-[10px] font-semibold">
        AFTER
      </div>
    </div>
  )
}
