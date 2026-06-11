import { useEffect } from 'react'
import { motion } from 'framer-motion'
import confetti from 'canvas-confetti'
import type { Achievement } from '../../types'

interface Props {
  achievement: Achievement
  onDone: () => void
}

export function AchievementPopup({ achievement, onDone }: Props) {
  useEffect(() => {
    confetti({ particleCount: 100, spread: 70, origin: { y: 0.5 }, colors: ['#6C47FF', '#FF2D78', '#FFD700'] })
    const t = setTimeout(onDone, 3200)
    return () => clearTimeout(t)
  }, [onDone])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
      onClick={onDone}
    >
      <motion.div
        initial={{ scale: 0.3, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.8, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 24 }}
        className="mx-6 rounded-[28px] p-7 text-center flex flex-col items-center gap-3"
        style={{ background: 'linear-gradient(145deg, #1C1C1E, #2C2C2E)', border: '1px solid rgba(255,255,255,0.1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <motion.div
          animate={{ rotate: [0, -8, 8, -8, 0], scale: [1, 1.15, 1] }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="text-[64px] leading-none"
        >
          {achievement.icon}
        </motion.div>
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#6C47FF]">Achievement Unlocked</p>
        <h3 className="text-[22px] font-bold text-white leading-tight">{achievement.title}</h3>
        <p className="text-[13px] text-white/60 leading-relaxed">{achievement.desc}</p>
        <div className="mt-1 px-5 py-2 rounded-full bg-[#6C47FF]/20 border border-[#6C47FF]/40">
          <span className="text-[12px] font-semibold text-[#A78BFA]">Tap to dismiss</span>
        </div>
      </motion.div>
    </motion.div>
  )
}
