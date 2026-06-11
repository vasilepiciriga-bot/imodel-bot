import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Check, Crown } from 'lucide-react'
import type { PhotoshootMode, PhotoshootModeKey } from '../../types'
import { track } from '../../api/analytics'

const PREMIUM_MODES = new Set(['vogue', 'ceo', 'luxury'])

const tg = window.Telegram?.WebApp

const BADGE_LABELS: Record<string, string> = {
  popular: '🔥 Popular',
  best_quality: '👑 Best Quality',
  for_business: '💼 Business',
  viral: '✨ Viral',
}

const MODE_COLORS: Record<PhotoshootModeKey, { from: string; to: string }> = {
  everyday: { from: '#6C47FF', to: '#8B67FF' },
  premium:  { from: '#6C47FF', to: '#FF2D78' },
  vogue:    { from: '#1A1A2E', to: '#8B0000' },
  ceo:      { from: '#1A3A5C', to: '#2E6CB5' },
  dating:   { from: '#FF6B6B', to: '#FFD93D' },
  luxury:   { from: '#B8860B', to: '#FFD700' },
  custom:   { from: '#0F2027', to: '#203A43' },
}

interface Props {
  open: boolean
  onClose: () => void
  onSelect: (mode: PhotoshootModeKey, customDesc?: string) => void
  onUpgrade?: () => void
  currentMode: PhotoshootModeKey
  userCredits: number
  modes: PhotoshootMode[]
}

export function PhotoshootModePicker({ open, onClose, onSelect, onUpgrade, currentMode, userCredits, modes }: Props) {
  const [selected, setSelected] = useState<PhotoshootModeKey>(currentMode)
  const [customDesc, setCustomDesc] = useState('')
  const [upgradeMode, setUpgradeMode] = useState<PhotoshootMode | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setSelected(currentMode)
    setUpgradeMode(null)
  }, [currentMode, open])

  // Android back button support
  useEffect(() => {
    if (!open) return
    window.history.pushState({ modePicker: true }, '')
    const onPop = () => { setUpgradeMode(null); onClose() }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [open, onClose])

  const selectedMode = modes.find((m) => m.key === selected)

  function handleModeSelect(mode: PhotoshootMode) {
    tg?.HapticFeedback?.selectionChanged()
    setSelected(mode.key)
    if (mode.key !== 'custom') setCustomDesc('')
    // Show inline upgrade sheet when premium mode + low credits
    if (PREMIUM_MODES.has(mode.key) && userCredits < 10) {
      track('premium_mode_upgrade_shown', { mode: mode.key, credits: userCredits })
      setUpgradeMode(mode)
    } else {
      setUpgradeMode(null)
    }
  }

  function handleConfirm() {
    tg?.HapticFeedback?.impactOccurred('medium')
    if (selected === 'custom' && !customDesc.trim()) {
      textareaRef.current?.focus()
      return
    }
    track('mode_selected', { mode: selected, credits: selectedMode?.credits })
    onSelect(selected, selected === 'custom' ? customDesc.trim() : undefined)
  }

  function handleUpgradeSubscribe() {
    track('premium_mode_subscribe_tapped', { mode: upgradeMode?.key })
    setUpgradeMode(null)
    onClose()
    onUpgrade?.()
  }

  function handleUpgradeUseCredits() {
    if (!upgradeMode) return
    tg?.HapticFeedback?.impactOccurred('medium')
    track('premium_mode_use_credits', { mode: upgradeMode.key, credits: userCredits })
    setUpgradeMode(null)
    onSelect(upgradeMode.key)
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50"
            onClick={onClose}
          />

          {/* Bottom sheet */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-[24px] shadow-2xl"
            style={{ maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-8 h-1 bg-gray-200 rounded-full" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-black/[0.06]">
              <h2 className="text-[17px] font-bold text-[#1D1D1F]">Choose Photoshoot</h2>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-full bg-[#F5F5F7] flex items-center justify-center"
              >
                <X size={16} className="text-[#6E6E73]" />
              </button>
            </div>

            {/* Mode list */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
              {modes.map((mode) => {
                const isSelected = selected === mode.key
                const colors = MODE_COLORS[mode.key] ?? MODE_COLORS.everyday
                const canAfford = userCredits >= mode.credits
                return (
                  <motion.button
                    key={mode.key}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleModeSelect(mode)}
                    className={`w-full flex items-center gap-3 p-3.5 rounded-[16px] border-2 transition-colors text-left ${
                      isSelected ? 'border-[#6C47FF]' : 'border-transparent bg-[#F5F5F7]'
                    }`}
                    style={isSelected ? { background: `linear-gradient(135deg, ${colors.from}12, ${colors.to}18)` } : {}}
                  >
                    {/* Emoji circle */}
                    <div
                      className="w-12 h-12 rounded-[12px] flex items-center justify-center text-[24px] flex-shrink-0"
                      style={{ background: `linear-gradient(135deg, ${colors.from}, ${colors.to})` }}
                    >
                      {mode.emoji}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[15px] font-semibold text-[#1D1D1F]">{mode.label}</span>
                        {PREMIUM_MODES.has(mode.key) && (
                          <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-gradient-to-r from-[#FF9500] to-[#FF2D78] text-white">
                            <Crown size={8} strokeWidth={3} />PRO
                          </span>
                        )}
                        {mode.badge && !PREMIUM_MODES.has(mode.key) && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white">
                            {BADGE_LABELS[mode.badge] ?? mode.badge}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-[#6E6E73] mt-0.5 truncate">{mode.short_desc}</p>
                    </div>

                    {/* Cost + check */}
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span
                        className={`text-[13px] font-bold ${canAfford ? 'text-[#6C47FF]' : 'text-[#FF3B30]'}`}
                      >
                        {mode.credits}⚡
                      </span>
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-[#6C47FF] flex items-center justify-center">
                          <Check size={11} className="text-white" strokeWidth={3} />
                        </div>
                      )}
                    </div>
                  </motion.button>
                )
              })}

              {/* Custom mode: inline textarea */}
              <AnimatePresence>
                {selected === 'custom' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="pt-1 pb-2">
                      <textarea
                        ref={textareaRef}
                        value={customDesc}
                        onChange={(e) => setCustomDesc(e.target.value)}
                        placeholder="Describe your vision... (e.g. «business portrait in New York», «summer at the beach», «fashion editorial»)"
                        rows={3}
                        className="w-full px-4 py-3 rounded-[14px] bg-[#F5F5F7] text-[13px] text-[#1D1D1F] placeholder-[#6E6E73] resize-none outline-none border border-[#6C47FF]/30 focus:border-[#6C47FF]"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Bottom padding */}
              <div className="h-2" />
            </div>

            {/* Bottom CTA — upgrade sheet or normal confirm */}
            <AnimatePresence mode="wait">
              {upgradeMode ? (
                <motion.div
                  key="upgrade"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                  className="px-4 pb-safe pt-3 border-t border-black/[0.06] space-y-2.5"
                >
                  {/* Mode preview info */}
                  <div className="flex items-center gap-3 px-3 py-2.5 rounded-[14px] bg-gradient-to-r from-[#6C47FF]/8 to-[#FF2D78]/8">
                    <span className="text-[26px]">{upgradeMode.emoji}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-bold text-[#1D1D1F]">
                        <Crown size={12} className="inline text-[#FF9500] mr-1" strokeWidth={2.5} />
                        {upgradeMode.label}
                      </p>
                      <p className="text-[11px] text-[#6E6E73] truncate">{upgradeMode.short_desc}</p>
                    </div>
                    <span className="text-[13px] font-bold text-[#FF9500]">{upgradeMode.credits}⚡</span>
                  </div>
                  {/* Two-button choice */}
                  <div className="flex gap-2">
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={handleUpgradeSubscribe}
                      className="flex-1 py-3 rounded-[14px] text-white text-[13px] font-bold"
                      style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
                    >
                      Subscribe →
                    </motion.button>
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={handleUpgradeUseCredits}
                      disabled={userCredits < upgradeMode.credits}
                      className={`flex-1 py-3 rounded-[14px] text-[13px] font-bold border-2 transition-opacity ${
                        userCredits >= upgradeMode.credits
                          ? 'border-[#6C47FF] text-[#6C47FF]'
                          : 'border-[#D1D1D6] text-[#6E6E73] opacity-50'
                      }`}
                    >
                      Use {upgradeMode.credits}⚡
                    </motion.button>
                  </div>
                  <button
                    onClick={() => setUpgradeMode(null)}
                    className="w-full text-center text-[12px] text-[#6E6E73] py-1"
                  >
                    ← Back to modes
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="confirm"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="px-4 pb-safe pt-3 border-t border-black/[0.06]"
                >
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={handleConfirm}
                    disabled={selected === 'custom' && !customDesc.trim()}
                    className={`w-full py-4 rounded-[16px] text-white text-[16px] font-semibold transition-opacity ${
                      selected === 'custom' && !customDesc.trim() ? 'opacity-40' : ''
                    }`}
                    style={{ background: 'linear-gradient(135deg, #6C47FF 0%, #FF2D78 100%)' }}
                  >
                    {selectedMode ? `Set ${selectedMode.label} · ${selectedMode.credits}⚡` : 'Set Mode'}
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
