import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { shareToCommunity } from '../api/community'
import { hap } from '../lib/haptics'
import { useBackButton } from '../hooks/useBackButton'
import type { Generation } from '../types'

interface Props {
  job: Generation
  onClose: () => void
  onShared: () => void
}

export function CommunityShareModal({ job, onClose, onShared }: Props) {
  const [label, setLabel] = useState('')
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'duplicate'>('idle')
  useBackButton(onClose)

  const imageUrl = job.hd_url ?? job.output_url ?? ''

  async function handleShare() {
    hap.medium()
    setState('loading')
    try {
      const res = await shareToCommunity(job.job_id, label.trim() || 'My Style')
      if (res.already_shared) {
        setState('duplicate')
      } else {
        hap.success()
        setState('success')
        onShared()
        setTimeout(onClose, 2400)
      }
    } catch {
      setState('idle')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[200] bg-black/70 flex items-end"
      style={{ maxWidth: 480, margin: '0 auto' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 80, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
        className="w-full bg-[#1C1C1E] rounded-t-[28px] overflow-hidden"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 24px)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pb-4">
          <h2 className="text-[18px] font-bold text-white">Share Your Look ✨</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center"
          >
            <X size={15} className="text-white/70" />
          </button>
        </div>

        {state === 'success' ? (
          /* Success state */
          <div className="flex flex-col items-center justify-center py-8 gap-3 relative">
            <style>{`
              @keyframes flyUp {
                0%   { transform: translateY(0) scale(1) rotate(0deg); opacity: 1; }
                100% { transform: translateY(-90px) scale(0.4) rotate(25deg); opacity: 0; }
              }
              .confetti-star { position: absolute; font-size: 28px; animation: flyUp 1.2s ease-out forwards; }
            `}</style>
            <span className="confetti-star" style={{ left: '30%', animationDelay: '0ms' }}>⭐</span>
            <span className="confetti-star" style={{ left: '50%', animationDelay: '120ms' }}>✨</span>
            <span className="confetti-star" style={{ left: '68%', animationDelay: '240ms' }}>🌟</span>
            <motion.div
              initial={{ scale: 0.7, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 400, damping: 18 }}
              className="text-[48px]"
            >
              🎉
            </motion.div>
            <p className="text-[18px] font-bold text-white">Your look is live!</p>
            <p className="text-[13px] text-[#34C759] font-semibold">+5 credits added ⚡</p>
            <p className="text-[12px] text-white/50 px-8 text-center">
              Others can now discover and use your style
            </p>
          </div>
        ) : state === 'duplicate' ? (
          /* Already shared */
          <div className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="text-[48px]">🔁</div>
            <p className="text-[16px] font-bold text-white">Already shared!</p>
            <p className="text-[12px] text-white/50 text-center px-8">
              This photo is already in the community gallery
            </p>
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={onClose}
              className="mt-2 px-8 py-3 rounded-[16px] bg-white/10 text-white text-[15px] font-semibold"
            >
              Got it
            </motion.button>
          </div>
        ) : (
          /* Idle / Loading */
          <div className="px-5 flex flex-col gap-4">
            {/* Photo preview */}
            {imageUrl && (
              <div className="rounded-[18px] overflow-hidden mx-auto" style={{ width: '60%', aspectRatio: '3/4' }}>
                <img src={imageUrl} alt="preview" className="w-full h-full object-cover" />
              </div>
            )}

            {/* Label input */}
            <div>
              <label className="text-[12px] text-white/50 mb-1.5 block">Name your style (optional)</label>
              <input
                type="text"
                maxLength={40}
                placeholder="My Studio Look"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full bg-white/[0.08] border border-white/[0.12] rounded-[14px] px-4 py-3 text-[14px] text-white placeholder-white/30 outline-none focus:border-[#6C47FF]/60"
              />
            </div>

            {/* CTA */}
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={handleShare}
              disabled={state === 'loading'}
              className="w-full py-4 rounded-[16px] text-white text-[16px] font-bold disabled:opacity-60"
              style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
            >
              {state === 'loading' ? (
                <span className="flex items-center justify-center gap-2">
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 0.8, ease: 'linear' }}
                    className="inline-block w-4 h-4 border-2 border-white/40 border-t-white rounded-full"
                  />
                  Sharing…
                </span>
              ) : (
                '✨ Share to Community'
              )}
            </motion.button>
            <p className="text-[11px] text-white/35 text-center -mt-2">
              Others can see this photo and use the same prompt
            </p>
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
