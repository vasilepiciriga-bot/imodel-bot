import { createContext, useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, AlertCircle, CheckCircle2, Info } from 'lucide-react'
import { hap } from '../../lib/haptics'

export type ToastType = 'success' | 'error' | 'info' | 'reward'

export interface ToastOptions {
  icon?: string
  sub?: string
  duration?: number
  retry?: () => void
}

interface ToastItem extends ToastOptions {
  id: string
  type: ToastType
  message: string
}

interface ToastAPI {
  success: (message: string, opts?: ToastOptions) => void
  error:   (message: string, opts?: ToastOptions) => void
  info:    (message: string, opts?: ToastOptions) => void
  reward:  (message: string, opts?: ToastOptions) => void
}

export const ToastContext = createContext<ToastAPI | null>(null)

const TYPE_CONFIG = {
  success: {
    bg: 'bg-white',
    border: 'border-[#34C759]/40',
    icon: <CheckCircle2 size={18} className="text-[#34C759] flex-shrink-0" />,
  },
  error: {
    bg: 'bg-white',
    border: 'border-[#FF3B30]/30',
    icon: <AlertCircle size={18} className="text-[#FF3B30] flex-shrink-0" />,
  },
  info: {
    bg: 'bg-white',
    border: 'border-[#6C47FF]/20',
    icon: <Info size={18} className="text-[#6C47FF] flex-shrink-0" />,
  },
  reward: {
    bg: 'bg-gradient-to-r from-[#6C47FF] to-[#FF2D78]',
    border: 'border-transparent',
    icon: null,
  },
}

function ToastItem({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const cfg = TYPE_CONFIG[item.type]
  const isReward = item.type === 'reward'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -56, scale: 0.94 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -40, scale: 0.96 }}
      transition={{ type: 'spring', stiffness: 420, damping: 28 }}
      drag="y"
      dragConstraints={{ top: 0, bottom: 0 }}
      dragElastic={{ top: 0.3, bottom: 0 }}
      onDragEnd={(_, info) => { if (info.offset.y < -24) onDismiss(item.id) }}
      className={`mx-4 rounded-[18px] border px-4 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.14)] flex items-start gap-3 ${cfg.bg} ${cfg.border}`}
      style={{ backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)' }}
    >
      {item.icon ? (
        <span className="text-[20px] flex-shrink-0 mt-0.5">{item.icon}</span>
      ) : cfg.icon ? (
        <span className="mt-0.5">{cfg.icon}</span>
      ) : null}

      <div className="flex-1 min-w-0">
        <p className={`text-[14px] font-semibold leading-snug ${isReward ? 'text-white' : 'text-[#1D1D1F]'}`}>
          {item.message}
        </p>
        {item.sub && (
          <p className={`text-[12px] mt-0.5 ${isReward ? 'text-white/80' : 'text-[#6E6E73]'}`}>{item.sub}</p>
        )}
        {item.retry && (
          <button
            onClick={() => { item.retry?.(); onDismiss(item.id) }}
            className="mt-1.5 text-[12px] font-semibold text-[#6C47FF]"
          >
            Try again →
          </button>
        )}
      </div>

      <button onClick={() => onDismiss(item.id)} className="mt-0.5 flex-shrink-0">
        <X size={15} className={isReward ? 'text-white/70' : 'text-[#C7C7CC]'} />
      </button>
    </motion.div>
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timerRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const dismiss = useCallback((id: string) => {
    clearTimeout(timerRef.current[id])
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const show = useCallback((type: ToastType, message: string, opts: ToastOptions = {}) => {
    const id = `${Date.now()}-${Math.random()}`
    const duration = opts.duration ?? (type === 'error' ? 5000 : 3500)

    if (type === 'success' || type === 'reward') hap.success()
    if (type === 'error') hap.error()

    setToasts((prev) => [{ id, type, message, ...opts }, ...prev].slice(0, 4))
    timerRef.current[id] = setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  const api: ToastAPI = {
    success: (m, o) => show('success', m, o),
    error:   (m, o) => show('error', m, o),
    info:    (m, o) => show('info', m, o),
    reward:  (m, o) => show('reward', m, o),
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed top-3 inset-x-0 z-[200] flex flex-col gap-2 pointer-events-none" style={{ maxWidth: 480, margin: '0 auto' }}>
        <AnimatePresence>
          {toasts.map((t) => (
            <div key={t.id} className="pointer-events-auto">
              <ToastItem item={t} onDismiss={dismiss} />
            </div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
