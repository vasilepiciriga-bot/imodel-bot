import { motion } from 'framer-motion'
import { AlertCircle, RotateCcw } from 'lucide-react'

interface Props {
  message?: string
  onRetry?: () => void
  compact?: boolean
}

export function ErrorCard({ message = 'Something went wrong', onRetry, compact }: Props) {
  if (compact) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-[12px] bg-[#FF3B30]/8 border border-[#FF3B30]/20">
        <AlertCircle size={14} className="text-[#FF3B30] flex-shrink-0" />
        <p className="text-[12px] text-[#FF3B30] font-medium flex-1">{message}</p>
        {onRetry && (
          <motion.button whileTap={{ scale: 0.94 }} onClick={onRetry}
            className="text-[12px] font-semibold text-[#FF3B30] underline">
            Retry
          </motion.button>
        )}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center gap-3 py-6 px-4 rounded-[20px] bg-[#FF3B30]/6 border border-[#FF3B30]/15"
    >
      <div className="w-12 h-12 rounded-full bg-[#FF3B30]/12 flex items-center justify-center">
        <AlertCircle size={22} className="text-[#FF3B30]" />
      </div>
      <p className="text-[14px] font-semibold text-[#1D1D1F] text-center">{message}</p>
      {onRetry && (
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={onRetry}
          className="flex items-center gap-1.5 px-5 py-2.5 rounded-full bg-[#FF3B30] text-white text-[13px] font-semibold"
        >
          <RotateCcw size={13} /> Try again
        </motion.button>
      )}
    </motion.div>
  )
}
