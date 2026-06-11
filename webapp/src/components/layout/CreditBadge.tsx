import { motion } from 'framer-motion'
import { Zap } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

const tg = window.Telegram?.WebApp

export function CreditBadge() {
  const credits = useAppStore((s) => s.user?.credits ?? 0)
  const setTab = useAppStore((s) => s.setTab)

  return (
    <motion.button
      whileTap={{ scale: 0.92 }}
      onClick={() => {
        tg?.HapticFeedback?.impactOccurred('light')
        setTab('shop')
      }}
      className="flex items-center gap-1 px-3 py-1.5 rounded-pill bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white shadow"
    >
      <Zap size={13} fill="white" strokeWidth={0} />
      <span className="text-[13px] font-semibold">{credits}</span>
    </motion.button>
  )
}
