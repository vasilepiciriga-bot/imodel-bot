import { motion } from 'framer-motion'

const STEPS = ['Uploading photo...', 'Detecting face...', 'Generating...', 'Final touch...']

interface Props {
  step: number
}

export function ProgressRing({ step }: Props) {
  const r = 32
  const circ = 2 * Math.PI * r
  const progress = Math.min(step / 3, 1)

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
        key={step}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-[14px] text-[#6E6E73] font-medium"
      >
        {STEPS[Math.min(step, STEPS.length - 1)]}
      </motion.p>
    </div>
  )
}
