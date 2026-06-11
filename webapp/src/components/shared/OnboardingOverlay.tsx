import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { track } from '../../api/analytics'

const STORAGE_KEY = 'imodel_onboarded_v1'

const SLIDES = [
  {
    emoji: '🤳',
    title: 'Upload your selfie',
    desc: 'One clear photo of your face — that\'s all we need. Good lighting works best.',
    accent: '#6C47FF',
  },
  {
    emoji: '🎨',
    title: 'Pick your photoshoot style',
    desc: 'Choose from Everyday, CEO, Vogue, Dating and more. Each mode crafts a different look.',
    accent: '#FF2D78',
  },
  {
    emoji: '✨',
    title: 'Generate & share',
    desc: 'AI creates studio-quality photos in seconds. Share to your Story or save to camera roll.',
    accent: '#FF9500',
  },
]

export function useOnboarding() {
  const done = typeof localStorage !== 'undefined' && !!localStorage.getItem(STORAGE_KEY)
  return !done
}

interface Props {
  onDone: () => void
}

export function OnboardingOverlay({ onDone }: Props) {
  const [slide, setSlide] = useState(0)
  const isLast = slide === SLIDES.length - 1
  const current = SLIDES[slide]

  function handleNext() {
    if (isLast) {
      localStorage.setItem(STORAGE_KEY, '1')
      track('onboarding_completed', { source: 'webapp' })
      onDone()
    } else {
      track('onboarding_step', { step: slide + 1 })
      setSlide((s) => s + 1)
    }
  }

  function handleSkip() {
    localStorage.setItem(STORAGE_KEY, '1')
    track('onboarding_skipped', { at_step: slide })
    onDone()
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex flex-col bg-[#F5F5F7]"
      style={{ maxWidth: 480, margin: '0 auto' }}
    >
      {/* Skip button */}
      <div className="flex justify-end px-5 pt-4">
        {!isLast && (
          <button
            onClick={handleSkip}
            className="text-[13px] text-[#6E6E73] font-medium py-1 px-2"
          >
            Skip
          </button>
        )}
      </div>

      {/* Slide content */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 pb-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={slide}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -40 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="flex flex-col items-center text-center"
          >
            {/* Emoji in colored circle */}
            <div
              className="w-28 h-28 rounded-[32px] flex items-center justify-center text-[56px] mb-8"
              style={{ background: `${current.accent}18`, boxShadow: `0 0 0 1px ${current.accent}22` }}
            >
              {current.emoji}
            </div>

            <h2 className="text-[26px] font-bold text-[#1D1D1F] leading-tight mb-3">
              {current.title}
            </h2>
            <p className="text-[15px] text-[#6E6E73] leading-relaxed max-w-[280px]">
              {current.desc}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Dots */}
      <div className="flex justify-center gap-2 pb-5">
        {SLIDES.map((_, i) => (
          <motion.div
            key={i}
            animate={{ width: i === slide ? 20 : 6, opacity: i === slide ? 1 : 0.3 }}
            transition={{ type: 'spring', stiffness: 400, damping: 28 }}
            className="h-1.5 rounded-full"
            style={{ backgroundColor: current.accent }}
          />
        ))}
      </div>

      {/* CTA */}
      <div className="px-5 pb-safe pb-6">
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleNext}
          className="w-full py-4 rounded-[18px] text-white text-[16px] font-semibold"
          style={{ background: `linear-gradient(135deg, ${current.accent} 0%, ${SLIDES[Math.min(slide + 1, SLIDES.length - 1)].accent} 100%)` }}
        >
          {isLast ? '🚀 Get started' : 'Next →'}
        </motion.button>
      </div>
    </motion.div>
  )
}
