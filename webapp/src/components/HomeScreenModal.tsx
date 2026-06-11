import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { track } from '../api/analytics'
import { claimQuest } from '../api/quests'
import { hap } from '../lib/haptics'

const tg = window.Telegram?.WebApp

interface Props {
  onClose(): void
  onCompleted(): void
}

const STEPS = [
  { emoji: '📱', num: '1', label: 'Open the app', sub: 'Tap the ⋯ menu at the top' },
  { emoji: '➕', num: '2', label: 'Add to screen', sub: 'Tap "Add to Home Screen"' },
  { emoji: '✅', num: '3', label: 'Confirm', sub: 'Press "Add" on the prompt' },
]

export function HomeScreenModal({ onClose, onCompleted }: Props) {
  const [state, setState] = useState<'idle' | 'checking' | 'success' | 'manual'>('idle')
  const [activeStep, setActiveStep] = useState(0)

  async function handleAdd() {
    hap.medium()
    setActiveStep(1)

    if (tg?.addToHomeScreen) {
      tg.addToHomeScreen()
      setState('checking')
      setTimeout(() => {
        tg.checkHomeScreenStatus?.((status) => {
          if (status === 'added' || status === 'unknown') {
            handleSuccess()
          } else if (status === 'unsupported') {
            setState('manual')
          } else {
            // missed — user dismissed, let them try again
            setState('idle')
            setActiveStep(0)
          }
        })
      }, 1500)
    } else {
      // Telegram doesn't support addToHomeScreen — show manual instructions
      setState('manual')
    }
  }

  async function handleManualConfirm() {
    hap.medium()
    setState('checking')
    track('home_screen_added')
    try {
      await claimQuest('add_to_home_screen')
    } catch { /* already claimed */ }
    setState('success')
    setTimeout(() => {
      onCompleted()
    }, 2200)
  }

  async function handleSuccess() {
    setActiveStep(2)
    track('home_screen_added')
    try {
      await claimQuest('add_to_home_screen')
    } catch { /* already claimed */ }
    setState('success')
    setTimeout(() => {
      onCompleted()
    }, 2200)
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] bg-black/70 flex items-end"
      style={{ maxWidth: 480, margin: '0 auto' }}
      onClick={state === 'idle' || state === 'manual' ? onClose : undefined}
    >
      <motion.div
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 80, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
        className="w-full bg-[#1C1C1E] rounded-t-[28px] overflow-hidden"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 28px)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>

        {state === 'success' ? (
          <div className="flex flex-col items-center py-10 gap-3 px-6">
            <style>{`
              @keyframes popIn { 0%{transform:scale(0.4);opacity:0} 60%{transform:scale(1.15)} 100%{transform:scale(1);opacity:1} }
              .pop-in { animation: popIn 0.45s cubic-bezier(.34,1.56,.64,1) forwards; }
            `}</style>
            <span className="text-[64px] pop-in">🏠</span>
            <p className="text-[20px] font-bold text-white text-center">App added!</p>
            <p className="text-[13px] text-[#34C759] font-semibold">+5 credits added ⚡</p>
            <p className="text-[12px] text-white/50 text-center mt-1">
              You can now open iModel Studio directly from your home screen
            </p>
          </div>
        ) : state === 'checking' ? (
          <div className="flex flex-col items-center py-12 gap-4">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
              className="w-8 h-8 border-2 border-white/20 border-t-[#6C47FF] rounded-full"
            />
            <p className="text-[14px] text-white/60">Checking…</p>
          </div>
        ) : state === 'manual' ? (
          /* Manual instructions — iOS / Android */
          <div className="px-5 pt-2 pb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[18px] font-bold text-white">Manual steps</h2>
              <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                <X size={15} className="text-white/70" />
              </button>
            </div>
            <div className="space-y-3 mb-5">
              {[
                { icon: '📱', text: 'Open this mini app in Telegram' },
                { icon: '⋯', text: 'Tap the ⋯ menu at the top right of Telegram' },
                { icon: '➕', text: 'Select "Add to Home Screen"' },
                { icon: '✅', text: 'Tap "Add" on the confirmation prompt' },
              ].map((step, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className="flex items-center gap-3 p-3 rounded-[14px]"
                  style={{ background: 'rgba(108,71,255,0.12)' }}
                >
                  <span className="text-[22px] w-8 text-center">{step.icon}</span>
                  <p className="text-[13px] text-white/90">{step.text}</p>
                </motion.div>
              ))}
            </div>
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={handleManualConfirm}
              className="w-full py-4 rounded-[16px] text-white text-[15px] font-bold"
              style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
            >
              ✅ I've added it — claim +5⚡
            </motion.button>
          </div>
        ) : (
          /* Default idle state */
          <div className="px-5 pt-2 pb-2">
            {/* Header */}
            <div className="flex items-center justify-between mb-1">
              <div>
                <h2 className="text-[20px] font-bold text-white">🏠 Add to Home Screen</h2>
                <p className="text-[13px] text-white/50 mt-0.5">Instant access · earn +5⚡ credits</p>
              </div>
              <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                <X size={15} className="text-white/70" />
              </button>
            </div>

            {/* Step cards */}
            <div className="flex gap-2.5 my-5">
              {STEPS.map((step, i) => {
                const isActive = activeStep === i
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.07, type: 'spring', stiffness: 380, damping: 26 }}
                    className="flex-1 rounded-[18px] p-3 flex flex-col items-center gap-1.5 text-center"
                    style={{
                      background: isActive
                        ? 'linear-gradient(160deg, #6C47FF, #9B59FF)'
                        : 'rgba(108,71,255,0.13)',
                      transition: 'background 0.3s ease',
                    }}
                  >
                    <span className="text-[28px]">{step.emoji}</span>
                    <span
                      className="text-[10px] font-bold uppercase tracking-widest"
                      style={{ color: isActive ? 'rgba(255,255,255,0.7)' : '#6C47FF' }}
                    >
                      Step {step.num}
                    </span>
                    <p className="text-[11px] font-semibold text-white leading-tight">{step.label}</p>
                    <p className="text-[9px] text-white/50 leading-tight">{step.sub}</p>
                  </motion.div>
                )
              })}
            </div>

            {/* CTA */}
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={handleAdd}
              className="w-full py-4 rounded-[16px] text-white text-[16px] font-bold mb-2"
              style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
            >
              🏠 Add Now · +5⚡
            </motion.button>
            <p className="text-[11px] text-white/35 text-center">
              Already added?{' '}
              <button
                className="text-[#A88FFF] underline"
                onClick={handleManualConfirm}
              >
                Tap here to claim
              </button>
            </p>
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
