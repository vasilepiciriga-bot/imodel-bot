import { motion } from 'framer-motion'
import { useAppStore } from '../../store/appStore'
import type { GenerationMode } from '../../types'

const MODES: { id: GenerationMode; label: string; emoji: string }[] = [
  { id: 'portrait', label: 'Portrait', emoji: '✦' },
  { id: 'copy_scene', label: 'Scene', emoji: '🎬' },
  { id: 'copy_image', label: 'Copy Image', emoji: '🖼️' },
]

const tg = window.Telegram?.WebApp

export function ModeSelector() {
  const mode = useAppStore((s) => s.mode)
  const setMode = useAppStore((s) => s.setMode)

  return (
    <div className="flex gap-2 p-1 bg-[#F5F5F7] rounded-xl">
      {MODES.map(({ id, label, emoji }) => (
        <button
          key={id}
          onClick={() => {
            tg?.HapticFeedback?.selectionChanged()
            setMode(id)
          }}
          className="relative flex-1 flex items-center justify-center gap-1 py-2 rounded-[10px] text-[13px] font-medium transition-colors"
          style={{ color: mode === id ? '#6C47FF' : '#6E6E73' }}
        >
          {mode === id && (
            <motion.div
              layoutId="mode-bg"
              className="absolute inset-0 bg-white rounded-[10px] shadow-sm"
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}
          <span className="relative z-10">{emoji}</span>
          <span className="relative z-10">{label}</span>
        </button>
      ))}
    </div>
  )
}
