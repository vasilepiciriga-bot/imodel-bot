import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import type { LeaderboardData } from '../../api/leaderboard'

const MEDALS = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

interface Props {
  data: LeaderboardData
  onClose: () => void
}

export function LeaderboardModal({ data, onClose }: Props) {
  const period = data.period === '7d' ? 'This week' : 'All time'
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col bg-black/80"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', stiffness: 320, damping: 32 }}
        className="mt-auto bg-[#1C1C1E] rounded-t-[24px] pb-safe"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-8 h-1 bg-white/20 rounded-full" />
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div>
            <h2 className="text-[17px] font-bold text-white">🏆 Leaderboard</h2>
            <p className="text-[12px] text-white/50 mt-0.5">{period} · top generators</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
            <X size={16} className="text-white/70" />
          </button>
        </div>
        <div className="px-4 py-3 space-y-1 max-h-[60vh] overflow-y-auto">
          {data.entries.map((e) => (
            <motion.div
              key={e.rank}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: e.rank * 0.04 }}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-[12px] ${
                e.is_me ? 'bg-[#6C47FF]/20 border border-[#6C47FF]/40' : 'bg-white/5'
              }`}
            >
              <span className="text-[20px] w-7 text-center">{MEDALS[e.rank - 1] ?? `#${e.rank}`}</span>
              <span className={`flex-1 text-[14px] font-medium ${e.is_me ? 'text-[#A88FFF]' : 'text-white'}`}>
                {e.display_name}{e.is_me ? ' · you' : ''}
              </span>
              <span className="text-[13px] text-white/60 font-semibold">{e.gens}⚡</span>
            </motion.div>
          ))}
          {data.my_rank && data.my_rank > 10 && (
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-[12px] bg-[#6C47FF]/10 border border-[#6C47FF]/20 mt-3">
              <span className="text-[20px] w-7 text-center">#{data.my_rank}</span>
              <span className="flex-1 text-[14px] font-medium text-[#A88FFF]">You</span>
              <span className="text-[13px] text-white/60 font-semibold">{data.my_gens}⚡</span>
            </div>
          )}
        </div>
        <div className="px-4 pb-4 pt-2">
          <p className="text-[11px] text-white/30 text-center">Generate more photos to climb the ranks ✦</p>
        </div>
      </motion.div>
    </motion.div>
  )
}
