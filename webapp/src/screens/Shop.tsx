import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, Zap, Crown, Star } from 'lucide-react'
import confetti from 'canvas-confetti'
import { getShop, createInvoice, type ShopData } from '../api/shop'
import { getMe } from '../api/session'
import { useAppStore } from '../store/appStore'
import { track } from '../api/analytics'
import { useToast } from '../hooks/useToast'

const tg = window.Telegram?.WebApp

const SHOP_CACHE_KEY = 'imodel_shop_v1'
const SHOP_TTL = 5 * 60 * 1000

async function getShopCached(): Promise<ShopData> {
  try {
    const raw = localStorage.getItem(SHOP_CACHE_KEY)
    if (raw) {
      const { ts, data } = JSON.parse(raw)
      if (Date.now() - ts < SHOP_TTL) return data
    }
  } catch {}
  const data = await getShop()
  localStorage.setItem(SHOP_CACHE_KEY, JSON.stringify({ ts: Date.now(), data }))
  return data
}

function fireConfetti() {
  confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 }, colors: ['#6C47FF', '#FF2D78', '#FFD700'] })
}

export default function Shop() {
  const [shop, setShop] = useState<ShopData | null>(null)
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const updateCredits = useAppStore((s) => s.updateCredits)
  const toast = useToast()

  useEffect(() => {
    getShopCached().then(setShop).catch(() => null)
  }, [])

  const handleBuy = useCallback(async (itemId: string, stars?: number) => {
    tg?.HapticFeedback?.impactOccurred('medium')
    track('buy_tapped', { pack: itemId, stars: stars ?? 0 })
    try {
      const { invoice_url } = await createInvoice(itemId)
      tg?.openInvoice(invoice_url, async (status: string) => {
        if (status === 'paid') {
          fireConfetti()
          tg?.HapticFeedback?.notificationOccurred('success')
          const updated = await getMe()
          setUser(updated)
          updateCredits(updated.credits)
          localStorage.removeItem(SHOP_CACHE_KEY)
          const freshShop = await getShop()
          setShop(freshShop)
        }
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Purchase failed'
      toast.error(msg)
    }
  }, [setUser, updateCredits, toast])

  const credits = user?.credits ?? 0
  const activePlan = shop?.subscription

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 pt-4 pb-2">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🛍 Shop</h1>
      </div>

      <div className="flex-1 px-4 pb-6 space-y-5">
        {/* Balance hero */}
        <div className="p-5 rounded-card bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] text-white text-center">
          <p className="text-[13px] opacity-80 font-medium">Your balance</p>
          <p className="text-[48px] font-bold leading-none mt-1">{credits}</p>
          <p className="text-[13px] opacity-80 mt-1">generations remaining</p>
          {credits <= 5 && (
            <motion.p
              animate={{ opacity: [0.7, 1, 0.7] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className="text-[12px] mt-2 font-semibold"
            >
              ⚡ Running low — top up now
            </motion.p>
          )}
        </div>

        {/* Subscriptions */}
        <div>
          <p className="text-[13px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2">Subscriptions</p>
          <div className="space-y-2">
            {(shop?.subscriptions ?? []).map((sub) => {
              const isActive = activePlan?.plan === sub.id
              return (
                <motion.button
                  key={sub.id}
                  whileTap={isActive ? {} : { scale: 0.98 }}
                  disabled={isActive}
                  onClick={() => handleBuy(sub.id, sub.stars)}
                  className={`w-full flex items-center justify-between p-4 rounded-card border-2 ${
                    isActive ? 'border-[#34C759] bg-[#34C759]/5' : 'border-[#6C47FF]/20 bg-white'
                  }`}
                >
                  <div className="text-left">
                    <div className="flex items-center gap-2">
                      <Crown size={16} className={isActive ? 'text-[#34C759]' : 'text-[#6C47FF]'} />
                      <span className="text-[15px] font-semibold text-[#1D1D1F]">{sub.label}</span>
                    </div>
                    <p className="text-[12px] text-[#6E6E73] mt-0.5">{sub.credits} generations · auto-renew</p>
                    {isActive && activePlan?.expiry && (
                      <p className="text-[11px] text-[#34C759] mt-0.5">
                        ✓ Active until {new Date(activePlan.expiry).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  {isActive ? (
                    <CheckCircle2 size={22} className="text-[#34C759]" />
                  ) : (
                    <div className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] rounded-pill text-white text-[13px] font-semibold">
                      <Star size={12} fill="white" strokeWidth={0} /> {sub.stars}
                    </div>
                  )}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* Credit packs */}
        <div>
          <p className="text-[13px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2">Credit Packs</p>
          <div className="grid grid-cols-2 gap-2">
            {(shop?.packs ?? []).map((pack) => (
              <motion.button
                key={pack.id}
                whileTap={{ scale: 0.96 }}
                onClick={() => handleBuy(pack.id, pack.stars)}
                className="p-4 rounded-card bg-white border border-black/[0.06] shadow-card text-left"
              >
                <div className="flex items-center gap-1 mb-1">
                  <Zap size={14} className="text-[#6C47FF]" fill="#6C47FF" strokeWidth={0} />
                  <span className="text-[20px] font-bold text-[#1D1D1F]">{pack.credits}</span>
                </div>
                <p className="text-[11px] text-[#6E6E73]">generations</p>
                <p className="mt-2 text-[13px] font-semibold text-[#6C47FF]">{pack.stars} ★</p>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Preset Packs */}
        {(shop?.preset_packs ?? []).some((p) => !p.unlocked) && (
          <div>
            <p className="text-[13px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2">Preset Packs</p>
            <div className="space-y-2">
              {(shop?.preset_packs ?? []).filter((p) => !p.unlocked).map((pack) => (
                <motion.button
                  key={pack.id}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => handleBuy(pack.id, pack.stars)}
                  className="w-full flex items-center gap-3 p-4 rounded-card bg-gradient-to-r from-[#FF9500]/10 to-[#6C47FF]/10 border border-[#FF9500]/20"
                >
                  <span className="text-2xl">{pack.emoji}</span>
                  <div className="flex-1 text-left">
                    <p className="text-[14px] font-semibold text-[#1D1D1F]">{pack.label}</p>
                    <p className="text-[11px] text-[#6E6E73]">{pack.presets_count} presets · one-time unlock</p>
                  </div>
                  <span className="text-[14px] font-bold text-[#6C47FF]">{pack.stars}★</span>
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {/* Power-ups */}
        <div>
          <p className="text-[13px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2">Power-Ups</p>
          <div className="space-y-2">
            {/* Style Pack */}
            {shop && !(user?.unlocked_packs ?? []).includes('premium_pack_1') && (
              <motion.button
                whileTap={{ scale: 0.98 }}
                onClick={() => handleBuy('premium_pack_1', shop?.style_packs?.find(p => p.id === 'premium_pack_1')?.stars ?? 490)}
                className="w-full flex items-center gap-3 p-4 rounded-card bg-gradient-to-r from-[#6C47FF]/10 to-[#FF2D78]/10 border border-[#6C47FF]/20"
              >
                <span className="text-2xl">🎨</span>
                <div className="flex-1 text-left">
                  <p className="text-[14px] font-semibold text-[#1D1D1F]">Premium Style Pack</p>
                  <p className="text-[11px] text-[#6E6E73]">15 exclusive styles · one-time unlock</p>
                </div>
                <span className="text-[14px] font-bold text-[#6C47FF]">{shop?.style_packs?.find(p => p.id === 'premium_pack_1')?.stars ?? 490}★</span>
              </motion.button>
            )}

            {/* Age Pack */}
            {shop && !user?.age_pack && (
              <motion.button
                whileTap={{ scale: 0.98 }}
                onClick={() => handleBuy('age_pack', shop?.style_packs?.find(p => p.id === 'age_pack')?.stars ?? 290)}
                className="w-full flex items-center gap-3 p-4 rounded-card bg-gradient-to-r from-[#FF9500]/10 to-[#FF2D78]/10 border border-[#FF9500]/20"
              >
                <span className="text-2xl">🎭</span>
                <div className="flex-1 text-left">
                  <p className="text-[14px] font-semibold text-[#1D1D1F]">Age Magic Pack</p>
                  <p className="text-[11px] text-[#6E6E73]">Young/Old filters · 4 styles · one-time</p>
                </div>
                <span className="text-[14px] font-bold text-[#FF9500]">{shop?.style_packs?.find(p => p.id === 'age_pack')?.stars ?? 290}★</span>
              </motion.button>
            )}

            {/* Feature info */}
            <div className="flex gap-2">
              <div className="flex-1 p-3 rounded-card bg-[#F5F5F7]">
                <p className="text-[13px] font-semibold text-[#1D1D1F]">🎯 Batch ×4</p>
                <p className="text-[11px] text-[#6E6E73] mt-0.5">3 credits → 4 variations</p>
                <p className="text-[11px] text-[#34C759] mt-1 font-medium">Free feature</p>
              </div>
              <div className="flex-1 p-3 rounded-card bg-[#F5F5F7]">
                <p className="text-[13px] font-semibold text-[#1D1D1F]">💎 HD Upscale</p>
                <p className="text-[11px] text-[#6E6E73] mt-0.5">+2 credits per photo</p>
                <p className="text-[11px] text-[#34C759] mt-1 font-medium">Free feature</p>
              </div>
            </div>
          </div>
        </div>

        {/* Referral */}
        <div className="p-4 rounded-card bg-[#F5F5F7]">
          <p className="text-[15px] font-semibold text-[#1D1D1F]">🎁 Invite Friends</p>
          <p className="text-[12px] text-[#6E6E73] mt-1">Get 3 free generations per friend</p>
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={() => {
              const link = `https://t.me/share/url?url=https://t.me/imodelbot?start=ref_${user?.uid}&text=AI+photo+generator!`
              tg?.openLink(link)
            }}
            className="mt-3 w-full py-2.5 rounded-pill bg-white border border-black/[0.08] text-[13px] font-medium text-[#1D1D1F]"
          >
            Share Invite Link
          </motion.button>
        </div>
      </div>
    </div>
  )
}
