import { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Camera, ChevronRight } from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import { track } from '../../api/analytics'
import type { Preset } from '../../types'

const tg = window.Telegram?.WebApp
const STORAGE_KEY = 'imodel_onboarded_v2'

const FEATURED: Preset[] = [
  { key: 'golden_hour', emoji: '🌅', label: 'Golden Hour', category: 'outdoor',   is_premium: false },
  { key: 'neon_night',  emoji: '🌃', label: 'Neon Night',  category: 'cinematic', is_premium: false },
  { key: 'headshot',    emoji: '👔', label: 'Headshot',    category: 'studio',    is_premium: false },
  { key: 'soft_glam',   emoji: '✨', label: 'Soft Glam',   category: 'lifestyle', is_premium: false },
  { key: 'cinematic',   emoji: '🎬', label: 'Cinematic',   category: 'cinematic', is_premium: false },
  { key: 'beach',       emoji: '🏖', label: 'Beach',       category: 'outdoor',   is_premium: false },
]

const ACCENT: Record<string, string> = {
  outdoor:   '#059669',
  cinematic: '#7C3AED',
  studio:    '#3B82F6',
  lifestyle: '#D97706',
}

export function useOnboarding() {
  if (typeof localStorage === 'undefined') return false
  // v1 users are also considered done
  return !localStorage.getItem(STORAGE_KEY) && !localStorage.getItem('imodel_onboarded_v1')
}

interface Props { onDone: () => void }

export function OnboardingOverlay({ onDone }: Props) {
  const [step, setStep] = useState(0)                      // 0: style, 1: selfie
  const [selected, setSelected] = useState<Preset | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [b64, setB64] = useState<string | null>(null)
  const [completing, setCompleting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const setSelfie     = useAppStore((s) => s.setSelfie)
  const setActivePreset = useAppStore((s) => s.setActivePreset)
  const setTab        = useAppStore((s) => s.setTab)

  function dismiss() {
    localStorage.setItem(STORAGE_KEY, '1')
    track('onboarding_skipped', { at_step: step })
    onDone()
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const result = ev.target?.result as string
      setPreview(result)
      setB64(result.split(',')[1])
    }
    reader.readAsDataURL(file)
  }

  function handleComplete() {
    if (!selected || !b64 || !preview || completing) return
    setCompleting(true)
    tg?.HapticFeedback?.notificationOccurred('success')
    track('onboarding_completed', { style: selected.key, source: 'webapp' })
    localStorage.setItem(STORAGE_KEY, '1')
    setActivePreset(selected)
    setSelfie(b64, preview)
    setTimeout(() => { setTab('studio'); onDone() }, 900)
  }

  if (completing) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-6 bg-[#F5F5F7]"
        style={{ maxWidth: 480, margin: '0 auto' }}
      >
        <motion.div
          initial={{ scale: 0.4, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
          className="w-24 h-24 rounded-[32px] bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] flex items-center justify-center text-[48px]"
        >
          ✨
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-center px-8"
        >
          <p className="text-[24px] font-bold text-[#1D1D1F]">Opening Studio…</p>
          <p className="text-[14px] text-[#6E6E73] mt-1.5">
            Your <span className="font-semibold">{selected?.label}</span> look is ready to go
          </p>
        </motion.div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex flex-col bg-[#F5F5F7]"
      style={{ maxWidth: 480, margin: '0 auto' }}
    >
      {/* Progress bar */}
      <div className="h-1 bg-[#E5E5EA]">
        <motion.div
          className="h-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] rounded-r-full"
          animate={{ width: `${(step + 1) / 2 * 100}%` }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
        />
      </div>

      {/* Header row */}
      <div className="flex items-center justify-between px-5 pt-4 pb-1">
        <div className="flex gap-1.5 items-center">
          {[0, 1].map((i) => (
            <motion.div
              key={i}
              animate={{ width: i === step ? 24 : 8, opacity: i <= step ? 1 : 0.25 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className="h-1.5 rounded-full bg-[#6C47FF]"
            />
          ))}
          <span className="text-[12px] text-[#6E6E73] ml-1">Step {step + 1} of 2</span>
        </div>
        <button onClick={dismiss} className="text-[13px] text-[#6E6E73] font-medium py-1 px-2">
          Skip
        </button>
      </div>

      <AnimatePresence mode="wait">
        {/* ── Step 0: Style picker ── */}
        {step === 0 && (
          <motion.div
            key="style"
            initial={{ opacity: 0, x: 48 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -48 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="flex-1 flex flex-col px-5 pb-5 overflow-hidden"
          >
            <div className="mt-3 mb-4">
              <h1 className="text-[26px] font-bold text-[#1D1D1F] leading-tight">What's your vibe?</h1>
              <p className="text-[14px] text-[#6E6E73] mt-1">Pick a style for your first AI photo</p>
            </div>

            <div className="flex-1 grid grid-cols-2 gap-3 overflow-y-auto pb-1">
              {FEATURED.map((p) => {
                const accent = ACCENT[p.category] ?? '#6C47FF'
                const active = selected?.key === p.key
                return (
                  <motion.button
                    key={p.key}
                    whileTap={{ scale: 0.94 }}
                    onClick={() => { tg?.HapticFeedback?.impactOccurred('light'); setSelected(p) }}
                    className="relative flex flex-col items-center justify-center gap-2.5 py-5 px-3 rounded-[20px] transition-colors"
                    style={{
                      background: active ? `${accent}14` : '#fff',
                      border: `2.5px solid ${active ? accent : 'transparent'}`,
                      boxShadow: active
                        ? `0 0 0 4px ${accent}18`
                        : '0 1px 3px rgba(0,0,0,0.07)',
                    }}
                  >
                    <div
                      className="w-14 h-14 rounded-2xl flex items-center justify-center text-[30px]"
                      style={{ background: `${accent}18` }}
                    >
                      {p.emoji}
                    </div>
                    <span className="text-[13px] font-semibold text-[#1D1D1F]">{p.label}</span>
                    {active && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute top-2.5 right-2.5 w-5 h-5 rounded-full flex items-center justify-center"
                        style={{ background: accent }}
                      >
                        <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                          <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </motion.div>
                    )}
                  </motion.button>
                )
              })}
            </div>

            <div className="pt-3">
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={() => {
                  if (!selected) return
                  track('onboarding_step', { step: 1, style: selected.key })
                  setStep(1)
                }}
                disabled={!selected}
                className="w-full py-4 rounded-[18px] text-white text-[16px] font-semibold bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] disabled:opacity-30 flex items-center justify-center gap-2"
              >
                Next <ChevronRight size={18} />
              </motion.button>
            </div>
          </motion.div>
        )}

        {/* ── Step 1: Selfie upload ── */}
        {step === 1 && (
          <motion.div
            key="selfie"
            initial={{ opacity: 0, x: 48 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -48 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="flex-1 flex flex-col px-5 pb-5"
          >
            <div className="mt-3 mb-4">
              <h1 className="text-[26px] font-bold text-[#1D1D1F] leading-tight">Add your selfie</h1>
              <p className="text-[14px] text-[#6E6E73] mt-1">Clear face photo · good lighting = best result</p>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center gap-3">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
              />

              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={() => fileRef.current?.click()}
                className="w-[220px] h-[220px] rounded-[28px] overflow-hidden relative flex-shrink-0"
                style={{
                  border: preview ? 'none' : '2.5px dashed #C7C7CC',
                  background: preview ? 'transparent' : '#fff',
                  boxShadow: preview ? '0 4px 20px rgba(0,0,0,0.12)' : 'none',
                }}
              >
                {preview ? (
                  <>
                    <img src={preview} alt="selfie" className="w-full h-full object-cover" />
                    <div className="absolute bottom-3 right-3 w-9 h-9 rounded-full bg-[#34C759] flex items-center justify-center shadow-lg">
                      <svg width="14" height="11" viewBox="0 0 14 11" fill="none">
                        <path d="M1 5.5L5 9.5L13 1.5" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full gap-3 px-4">
                    <div className="w-16 h-16 rounded-full bg-[#6C47FF]/10 flex items-center justify-center">
                      <Camera size={28} className="text-[#6C47FF]" />
                    </div>
                    <p className="text-[14px] font-semibold text-[#1D1D1F] text-center">Tap to upload</p>
                    <p className="text-[12px] text-[#6E6E73] text-center">Camera roll or take new</p>
                  </div>
                )}
              </motion.button>

              {preview && (
                <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  onClick={() => { setPreview(null); setB64(null) }}
                  className="text-[13px] text-[#6E6E73] font-medium"
                >
                  Change photo
                </motion.button>
              )}

              {/* Style reminder chip */}
              {selected && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-white shadow-sm"
                >
                  <span className="text-[18px]">{selected.emoji}</span>
                  <span className="text-[13px] font-medium text-[#1D1D1F]">{selected.label}</span>
                  <button
                    onClick={() => setStep(0)}
                    className="text-[11px] text-[#6C47FF] font-semibold ml-1"
                  >
                    Change
                  </button>
                </motion.div>
              )}
            </div>

            <div className="pt-3 space-y-2">
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={handleComplete}
                disabled={!b64}
                className="w-full py-4 rounded-[18px] text-white text-[16px] font-semibold bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] disabled:opacity-30"
              >
                🚀 Generate for free
              </motion.button>
              <p className="text-center text-[11px] text-[#6E6E73]">
                Uses 1 free credit · No subscription needed
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
