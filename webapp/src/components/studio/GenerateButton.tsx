import { motion } from 'framer-motion'
import { Sparkles, Loader2 } from 'lucide-react'

interface Props {
  onClick: () => void
  loading: boolean
  disabled: boolean
  cost: number
}

export function GenerateButton({ onClick, loading, disabled, cost }: Props) {
  return (
    <motion.button
      whileTap={disabled || loading ? {} : { scale: 0.97 }}
      onClick={onClick}
      disabled={disabled || loading}
      className="w-full py-4 rounded-card font-semibold text-[16px] text-white flex items-center justify-center gap-2 relative overflow-hidden"
      style={{
        background: disabled
          ? '#D1D1D6'
          : 'linear-gradient(135deg, #6C47FF 0%, #FF2D78 100%)',
        transition: 'background 0.2s',
      }}
    >
      {loading ? (
        <Loader2 size={20} className="animate-spin" />
      ) : (
        <>
          <Sparkles size={18} />
          <span>Generate</span>
          <span className="ml-1 px-2 py-0.5 rounded-full bg-white/20 text-[12px]">
            {cost} ⚡
          </span>
        </>
      )}
    </motion.button>
  )
}
