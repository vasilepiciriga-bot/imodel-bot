import { useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import confetti from 'canvas-confetti'
import { useBackButton } from '../../hooks/useBackButton'
import { useAppStore } from '../../store/appStore'
import { track } from '../../api/analytics'

const tg = window.Telegram?.WebApp

interface Props {
  resultUrl: string
  onClose: () => void
  onUpgrade: () => void
}

export function FirstGenModal({ resultUrl, onClose, onUpgrade }: Props) {
  const user = useAppStore((s) => s.user)
  const setTab = useAppStore((s) => s.setTab)
  useBackButton(onClose)

  useEffect(() => {
    confetti({ particleCount: 140, spread: 90, origin: { y: 0.55 }, colors: ['#6C47FF', '#FF2D78', '#FFD700', '#34C759'] })
    const t = setTimeout(onClose, 6000)
    return () => clearTimeout(t)
  }, [onClose])

  const handleShare = useCallback(() => {
    tg?.HapticFeedback?.impactOccurred('medium')
    track('first_gen_share_tapped')
    const botBase = user?.bot_link ?? 'https://t.me/imodelapp_bot'
    const refUrl = `${botBase}?start=ref_${user?.uid}`
    const link = `https://t.me/share/url?url=${encodeURIComponent(refUrl)}&text=${encodeURIComponent('AI photo generator — try it free! ✨')}`
    tg?.openLink(link)
    onClose()
  }, [user, onClose])

  const handleStyles = useCallback(() => {
    tg?.HapticFeedback?.impactOccurred('light')
    track('first_gen_styles_tapped')
    setTab('styles')
    onClose()
  }, [setTab, onClose])

  const handleUpgrade = useCallback(() => {
    tg?.HapticFeedback?.impactOccurred('medium')
    track('first_gen_upgrade_tapped')
    onUpgrade()
    onClose()
  }, [onUpgrade, onClose])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex flex-col"
    >
      {resultUrl ? (
        <>
          <img
            src={resultUrl}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
            style={{ filter: 'blur(18px) brightness(0.3)', transform: 'scale(1.1)' }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />
        </>
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-[#0F0F1A] to-[#1A0A2E]" />
      )}

      <div className="relative flex-1 flex flex-col items-center justify-end pb-safe pb-8 px-5 z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, type: 'spring', stiffness: 280, damping: 26 }}
          className="w-full max-w-[360px] space-y-4"
        >
          {/* Result thumbnail */}
          {resultUrl && (
            <div className="flex justify-center">
              <motion.div
                initial={{ scale: 0.7, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.05, type: 'spring', stiffness: 320, damping: 22 }}
                className="w-20 h-20 rounded-[20px] overflow-hidden border-2 border-white/30 shadow-2xl"
              >
                <img src={resultUrl} alt="Your first AI photo" className="w-full h-full object-cover" />
              </motion.div>
            </div>
          )}

          <div className="text-center">
            <h2 className="text-[26px] font-black text-white leading-tight">🎉 First photo done!</h2>
            <p className="text-[14px] text-white/60 mt-1.5">Share it and bring a friend — earn +3⚡ each</p>
          </div>

          <div className="space-y-2.5">
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={handleShare}
              className="w-full flex items-center justify-center gap-2 py-3.5 rounded-[16px] text-white font-bold text-[15px]"
              style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
            >
              Share & earn +3⚡
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={handleStyles}
              className="w-full flex items-center justify-center gap-2 py-3.5 rounded-[16px] bg-white/10 border border-white/15 text-white font-semibold text-[14px]"
            >
              Try another style →
            </motion.button>

            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={handleUpgrade}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-[16px] text-white/50 font-medium text-[13px]"
            >
              Upgrade for more
            </motion.button>
          </div>
        </motion.div>
      </div>
    </motion.div>
  )
}
