import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const HINTS = [
  'Reading your features...',
  'Matching lighting angles...',
  'Blending style layers...',
  'Perfecting skin tones...',
  'Adding depth and detail...',
  'Applying finishing touches...',
  'Almost ready...',
]

const STEP_LABEL_MAP: Record<string, string> = {
  analyzing:       'Analyzing selfie...',
  crafting_prompt: 'Building your prompt...',
  selecting:       'Selecting best shots...',
  upscaling:       'Enhancing quality...',
  ready:           'Done!',
}

function humanizeStepLabel(stepLabel: string): string {
  if (stepLabel.startsWith('generating_')) {
    const parts = stepLabel.split('_')
    if (parts.length === 4) return `Creating variation ${parts[1]} of ${parts[3]}...`
    return 'Generating...'
  }
  return STEP_LABEL_MAP[stepLabel] ?? 'Processing...'
}

function stepToProgress(stepLabel: string): number {
  if (stepLabel === 'analyzing' || stepLabel === 'crafting_prompt') return 0.1
  if (stepLabel.startsWith('generating_')) {
    const parts = stepLabel.split('_')
    if (parts.length === 4) {
      const cur = parseInt(parts[1], 10)
      const total = parseInt(parts[3], 10)
      if (total > 0) return 0.1 + (cur / total) * 0.6
    }
    return 0.4
  }
  if (stepLabel === 'selecting') return 0.75
  if (stepLabel === 'upscaling') return 0.9
  if (stepLabel === 'ready') return 1.0
  return 0.5
}

interface Props {
  selfiePreview: string
  stepLabel?: string
  step?: number
}

export function GeneratingCard({ selfiePreview, stepLabel, step = 0 }: Props) {
  const [hintIndex, setHintIndex] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setHintIndex((i) => (i + 1) % HINTS.length), 4000)
    return () => clearInterval(t)
  }, [])

  const progress = stepLabel ? stepToProgress(stepLabel) : Math.min(step / 3, 1)
  const pct = Math.round(progress * 100)
  const displayText = stepLabel ? humanizeStepLabel(stepLabel) : 'Processing...'

  return (
    <div className="relative w-full rounded-[20px] overflow-hidden" style={{ aspectRatio: '1 / 1' }}>
      {/* Blurred selfie background */}
      <img
        src={selfiePreview}
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
        style={{ filter: 'blur(16px) brightness(0.42)', transform: 'scale(1.14)' }}
      />

      {/* Scanning line */}
      <motion.div
        className="absolute left-0 right-0 h-[1.5px] pointer-events-none"
        style={{
          background:
            'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.75) 25%, rgba(255,255,255,0.75) 75%, transparent 100%)',
        }}
        initial={{ top: '0%' }}
        animate={{ top: '100%' }}
        transition={{ duration: 3, ease: 'linear', repeat: Infinity }}
      />

      {/* Glow bloom trailing the scan line */}
      <motion.div
        className="absolute left-0 right-0 h-16 pointer-events-none"
        style={{
          background: 'linear-gradient(to bottom, rgba(255,255,255,0.07), transparent)',
        }}
        initial={{ top: '-4rem' }}
        animate={{ top: '100%' }}
        transition={{ duration: 3, ease: 'linear', repeat: Infinity }}
      />

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6">
        <motion.span
          className="text-[48px] leading-none select-none"
          animate={{ rotate: 360 }}
          transition={{ duration: 4, ease: 'linear', repeat: Infinity }}
          style={{ display: 'block', filter: 'drop-shadow(0 0 16px rgba(108,71,255,0.95))' }}
        >
          ✦
        </motion.span>

        <AnimatePresence mode="wait">
          <motion.p
            key={stepLabel ?? 'default'}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
            className="text-[15px] font-semibold text-white text-center leading-snug"
          >
            {displayText}
          </motion.p>
        </AnimatePresence>

        <AnimatePresence mode="wait">
          <motion.p
            key={hintIndex}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.55 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
            className="text-[12px] text-white text-center"
          >
            {HINTS[hintIndex]}
          </motion.p>
        </AnimatePresence>
      </div>

      {/* Bottom progress bar */}
      <div
        className="absolute bottom-0 left-0 right-0 px-5 pb-4 pt-10"
        style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.65), transparent)' }}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex-1 h-[3px] rounded-full bg-white/20 overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{ background: 'linear-gradient(90deg, #6C47FF, #FF2D78)' }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            />
          </div>
          <span className="text-[11px] font-bold text-white/65 tabular-nums w-8 text-right">
            {pct}%
          </span>
        </div>
      </div>
    </div>
  )
}
