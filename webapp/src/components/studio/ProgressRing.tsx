import { motion } from 'framer-motion'

const LEGACY_STEPS = ['Uploading photo...', 'Detecting face...', 'Generating...', 'Final touch...']

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
  step?: number
  stepLabel?: string
}

export function ProgressRing({ step = 0, stepLabel }: Props) {
  const r = 32
  const circ = 2 * Math.PI * r

  const progress = stepLabel
    ? stepToProgress(stepLabel)
    : Math.min(step / 3, 1)

  const displayText = stepLabel
    ? humanizeStepLabel(stepLabel)
    : LEGACY_STEPS[Math.min(step, LEGACY_STEPS.length - 1)]

  const animKey = stepLabel ?? step

  return (
    <div className="flex flex-col items-center gap-4 py-8">
      <div className="relative w-20 h-20">
        <svg width="80" height="80" className="-rotate-90">
          <circle cx="40" cy="40" r={r} fill="none" stroke="#E5E5EA" strokeWidth="4" />
          <motion.circle
            cx="40"
            cy="40"
            r={r}
            fill="none"
            stroke="url(#grad)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={circ}
            animate={{ strokeDashoffset: circ * (1 - progress) }}
            transition={{ duration: 0.5, ease: 'easeInOut' }}
          />
          <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6C47FF" />
              <stop offset="100%" stopColor="#FF2D78" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl">✦</span>
        </div>
      </div>
      <motion.p
        key={String(animKey)}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-[14px] text-[#6E6E73] font-medium text-center px-4"
      >
        {displayText}
      </motion.p>
    </div>
  )
}
