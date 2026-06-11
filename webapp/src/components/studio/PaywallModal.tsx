import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import { X, Zap, Crown, Star } from 'lucide-react'
import confetti from 'canvas-confetti'
import { createInvoice } from '../../api/shop'
import { getMe } from '../../api/session'
import { useAppStore } from '../../store/appStore'
import { track } from '../../api/analytics'
import { useExperiment } from '../../hooks/useExperiment'
import { useToast } from '../../hooks/useToast'
import { useBackButton } from '../../hooks/useBackButton'

const tg = window.Telegram?.WebApp

const QUICK_PACKS = [
  { id: 'pack_10',  label: '10 gens',  stars: 199,  icon: <Zap size={16} className="text-[#6C47FF]" fill="#6C47FF" strokeWidth={0} /> },
  { id: 'pack_30',  label: '30 gens',  stars: 490,  icon: <Star size={16} className="text-[#FF9500]" fill="#FF9500" strokeWidth={0} /> },
  { id: 'pack_100', label: '100 gens', stars: 1290, icon: <Crown size={16} className="text-[#FF2D78]" /> },
] as const

type Segment = 'first' | 'active' | 'paid' | 'blocked'

function getSegment(gens: number, payments: number): Segment {
  if (payments > 0) return 'paid'
  if (gens >= 3) return 'active'
  if (gens >= 1) return 'first'
  return 'blocked'
}

// control copy (segment-aware)
const COPY: Record<Segment, { headline: string; sub: string }> = {
  first:   { headline: '✨ Free credits used', sub: 'Liked what you saw? The best results are still ahead.' },
  active:  { headline: '⚡ Out of generations', sub: "You're on a roll — keep creating with a pack." },
  paid:    { headline: '💎 Credits used up', sub: "You already know the quality. Don't stop now." },
  blocked: { headline: '💎 Out of credits', sub: 'Pick a plan to keep generating.' },
}
// urgency variant
const COPY_URGENCY: Record<Segment, { headline: string; sub: string }> = {
  first:   { headline: '⏳ Don\'t lose your momentum', sub: 'Get more credits now and keep your creative streak going.' },
  active:  { headline: '🔥 Keep the streak alive', sub: 'You\'re generating great photos — don\'t stop here.' },
  paid:    { headline: '⚡ Recharge before you forget', sub: 'Top up now and jump back in instantly.' },
  blocked: { headline: '⏳ Credits needed', sub: 'Grab a pack and generate your next photo right away.' },
}
// social proof variant
const COPY_SOCIAL: Record<Segment, { headline: string; sub: string }> = {
  first:   { headline: '✨ Join 10,000+ creators', sub: 'Most users upgrade after their first result. See why.' },
  active:  { headline: '⭐ Top creators generate daily', sub: 'Pick up a pack and stay ahead of the leaderboard.' },
  paid:    { headline: '💎 Power users never run dry', sub: 'Stay in the top 10% — recharge now.' },
  blocked: { headline: '📈 Thousands generate every day', sub: 'Pick a plan and keep creating with them.' },
}

interface Props {
  /** URL of the last generated image — used as blurred background */
  lastResultUrl?: string
  onClose: () => void
}

export function PaywallModal({ lastResultUrl, onClose }: Props) {
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const updateCredits = useAppStore((s) => s.updateCredits)
  const setTab = useAppStore((s) => s.setTab)
  const [buyingId, setBuyingId] = useState<string | null>(null)
  const toast = useToast()
  useBackButton(onClose)

  const gens = user?.gens_ok ?? 0
  const payments = user?.payments ?? 0
  const segment = getSegment(gens, payments)
  const paywallVariant = useExperiment('paywall_copy')
  const copyMap = paywallVariant === 'urgency' ? COPY_URGENCY
    : paywallVariant === 'social_proof' ? COPY_SOCIAL
    : COPY
  const { headline, sub } = copyMap[segment]

  const handleBuy = useCallback(async (packId: string, stars: number) => {
    tg?.HapticFeedback?.impactOccurred('medium')
    track('paywall_buy_tapped', { pack: packId, stars, segment, variant: paywallVariant })
    setBuyingId(packId)
    try {
      const { invoice_url } = await createInvoice(packId)
      tg?.openInvoice(invoice_url, async (status: string) => {
        if (status === 'paid') {
          confetti({ particleCount: 100, spread: 80, origin: { y: 0.6 }, colors: ['#6C47FF', '#FF2D78', '#FFD700'] })
          tg?.HapticFeedback?.notificationOccurred('success')
          track('paywall_converted', { pack: packId, stars, segment, variant: paywallVariant })
          const updated = await getMe()
          setUser(updated)
          updateCredits(updated.credits)
          onClose()
        }
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Purchase failed'
      toast.error(msg)
    } finally {
      setBuyingId(null)
    }
  }, [segment, setUser, updateCredits, onClose])

  function handleShopOpen() {
    track('paywall_shop_opened', { segment })
    setTab('shop')
    onClose()
  }

  function handleDismiss() {
    track('paywall_dismissed', { segment })
    onClose()
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[90] flex flex-col"
    >
      {/* Blurred background — last result or gradient */}
      {lastResultUrl ? (
        <>
          <img
            src={lastResultUrl}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
            style={{ filter: 'blur(20px) brightness(0.35)', transform: 'scale(1.1)' }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
        </>
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-[#0F0F1A] to-[#1A0A2E]" />
      )}

      {/* Dismiss */}
      <div className="relative flex justify-end px-4 pt-safe pt-4 z-10">
        <button
          onClick={handleDismiss}
          className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center"
        >
          <X size={16} className="text-white/70" />
        </button>
      </div>

      {/* Content */}
      <div className="relative flex-1 flex flex-col items-center justify-end pb-safe pb-6 px-5 z-10">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, type: 'spring', stiffness: 300, damping: 28 }}
          className="w-full max-w-[360px] space-y-4"
        >
          {/* Copy */}
          <div className="text-center mb-2">
            <h2 className="text-[24px] font-bold text-white leading-tight">{headline}</h2>
            <p className="text-[14px] text-white/60 mt-1.5">{sub}</p>
          </div>

          {/* Quick-buy packs */}
          <div className="space-y-2">
            {QUICK_PACKS.map((pack) => (
              <motion.button
                key={pack.id}
                whileTap={{ scale: 0.97 }}
                onClick={() => handleBuy(pack.id, pack.stars)}
                disabled={buyingId !== null}
                className="w-full flex items-center gap-3 px-4 py-3.5 rounded-[16px] bg-white/10 border border-white/15 backdrop-blur-sm disabled:opacity-60"
              >
                <span className="w-8 h-8 rounded-[10px] bg-white/10 flex items-center justify-center flex-shrink-0">
                  {pack.icon}
                </span>
                <span className="flex-1 text-left text-[15px] font-semibold text-white">{pack.label}</span>
                <div className="flex items-center gap-1 px-2.5 py-1 rounded-pill bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[13px] font-semibold">
                  {buyingId === pack.id ? '...' : `${pack.stars}★`}
                </div>
              </motion.button>
            ))}
          </div>

          {/* Secondary CTA */}
          <button
            onClick={handleShopOpen}
            className="w-full py-3 text-[14px] text-white/50 font-medium"
          >
            See all plans →
          </button>
        </motion.div>
      </div>
    </motion.div>
  )
}
