import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, Zap, Crown, Star, Check, ChevronRight, RotateCw } from 'lucide-react'
import confetti from 'canvas-confetti'
import { getShop, createInvoice, setAutoRecharge, type ShopData } from '../api/shop'
import { getMe, getMeFresh } from '../api/session'
import { useAppStore } from '../store/appStore'
import { track } from '../api/analytics'
import { useExperiment } from '../hooks/useExperiment'
import { getVariantSync } from '../api/experiments'
import { useToast } from '../hooks/useToast'
import { hap } from '../lib/haptics'

const tg = window.Telegram?.WebApp

const SHOP_CACHE_KEY = 'imodel_shop_v2'
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

const SUB_META: Record<string, { color: string; label: string; emoji: string; badge?: string }> = {
  sub_weekly:          { color: '#34C759',  label: 'Weekly',        emoji: '⚡' },
  sub_pro:             { color: '#6C47FF',  label: 'Pro',           emoji: '🚀', badge: 'Most Popular' },
  sub_creator:         { color: '#FF2D78',  label: 'Creator',       emoji: '🔥', badge: 'Best Value' },
  sub_elite:           { color: '#FF9500',  label: 'Elite',         emoji: '👑' },
  sub_pro_annual:      { color: '#6C47FF',  label: 'Pro Annual',    emoji: '🚀', badge: 'Save 20%' },
  sub_creator_annual:  { color: '#FF2D78',  label: 'Creator Annual',emoji: '🔥', badge: 'Best Deal ✓' },
}

const PACK_META: Record<string, { badge?: string; highlight?: boolean }> = {
  pack_10:  {},
  pack_30:  { badge: 'Popular' },
  pack_100: { badge: 'Best Value', highlight: true },
  pack_300: { badge: 'Pro Pick' },
}

function useCountdown(expiresAt: number) {
  const [remaining, setRemaining] = useState(() => Math.max(0, expiresAt - Math.floor(Date.now() / 1000)))
  useEffect(() => {
    if (remaining <= 0) return
    const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(t)
  }, [remaining])
  const h = Math.floor(remaining / 3600)
  const m = Math.floor((remaining % 3600) / 60)
  const s = remaining % 60
  const days = Math.floor(remaining / 86400)
  if (days >= 1) return `${days}d ${h % 24}h`
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function BundleCard({ bundle, onBuy }: { bundle: NonNullable<ShopData['bundle']>; onBuy: () => void }) {
  const countdown = useCountdown(bundle.expires_at)
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      onClick={onBuy}
      className="w-full text-left rounded-[20px] overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #FF6B00, #FF2D78)' }}
    >
      <div className="px-4 py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-white text-[15px] font-black">{bundle.label}</span>
              <span className="px-2 py-0.5 rounded-full bg-white/20 text-white text-[10px] font-bold">
                ⏰ {countdown}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {bundle.includes.map((item) => (
                <span key={item} className="flex items-center gap-1 text-white/90 text-[11px]">
                  <Check size={10} strokeWidth={3} className="text-white" />
                  {item}
                </span>
              ))}
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            <p className="text-white text-[20px] font-black leading-none">{bundle.stars}★</p>
            <p className="text-white/70 text-[10px]">limited</p>
          </div>
        </div>
      </div>
    </motion.button>
  )
}

export default function Shop() {
  const [shop, setShop] = useState<ShopData | null>(null)
  const [activeSubTab, setActiveSubTab] = useState<'monthly' | 'packs'>('monthly')
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly')
  const [autoRechargeEnabled, setAutoRechargeEnabled] = useState(false)
  const bundleVariant = useExperiment('bundle_position')
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const updateCredits = useAppStore((s) => s.updateCredits)
  const toast = useToast()

  useEffect(() => {
    getShopCached().then(setShop).catch(() => null)
    track('shop_opened', { variant: getVariantSync('bundle_position') })
  }, [])

  const handleBuy = useCallback(async (itemId: string, stars?: number) => {
    hap.medium()
    track('buy_tapped', { pack: itemId, stars: stars ?? 0, bundle_variant: bundleVariant })
    try {
      const { invoice_url } = await createInvoice(itemId)
      tg?.openInvoice(invoice_url, async (status: string) => {
        if (status === 'paid') {
          fireConfetti()
          hap.success()
          const updated = await getMeFresh()
          setUser(updated)
          updateCredits(updated.credits)
          localStorage.removeItem(SHOP_CACHE_KEY)
          const freshShop = await getShop()
          setShop(freshShop)
          toast.success('Purchase successful!', { icon: '🎉', sub: 'Credits added to your balance' })
        }
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Purchase failed'
      toast.error(msg)
    }
  }, [setUser, updateCredits, toast])

  const handleAutoRechargeToggle = useCallback(async () => {
    const next = !autoRechargeEnabled
    setAutoRechargeEnabled(next)
    hap.select()
    track('auto_recharge_toggled', { enabled: next })
    try {
      await setAutoRecharge('pack_30', 5, next)
      toast.success(next ? 'Auto-recharge enabled' : 'Auto-recharge disabled', {
        sub: next ? 'We\'ll remind you when credits run low' : undefined,
      })
    } catch {
      setAutoRechargeEnabled(!next)
    }
  }, [autoRechargeEnabled, toast])

  const credits = user?.credits ?? 0
  const activePlan = shop?.subscription

  const allFeatures = ['Generations', 'All styles', 'HD upscale', 'Priority queue', 'Batch ×4', 'Early access']
  const freeFeatures = ['5 free gens/day', 'All basic styles', 'Standard quality']

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-[#F5F5F7]">
      {/* Banner */}
      <AnimatePresence>
        {shop?.banner && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-gradient-to-r from-[#FF2D78] to-[#FF9500] px-4 py-2.5 text-white text-[12px] font-semibold text-center"
          >
            {shop.banner}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="px-4 pt-4 pb-1">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🛍 Shop</h1>
      </div>

      <div className="flex-1 px-4 pb-8 space-y-4">
        {/* Bundle at top — experiment: bundle_position=top */}
        {shop?.bundle && bundleVariant === 'top' && (
          <BundleCard bundle={shop.bundle} onBuy={() => handleBuy(shop!.bundle!.id, shop!.bundle!.stars)} />
        )}

        {/* Balance hero */}
        <div className="relative rounded-[24px] overflow-hidden p-5 text-white"
          style={{ background: 'linear-gradient(135deg, #6C47FF 0%, #FF2D78 100%)' }}>
          <div className="absolute top-0 right-0 w-40 h-40 rounded-full opacity-10 bg-white"
            style={{ transform: 'translate(30%, -30%)' }} />
          <p className="text-[12px] font-semibold opacity-80 uppercase tracking-widest">Your balance</p>
          <div className="flex items-end gap-2 mt-1">
            <span className="text-[52px] font-black leading-none">{credits}</span>
            <span className="text-[16px] font-medium opacity-80 mb-2">generations</span>
          </div>
          {credits <= 5 && (
            <motion.p
              animate={{ opacity: [0.7, 1, 0.7] }}
              transition={{ repeat: Infinity, duration: 1.4 }}
              className="text-[12px] font-semibold mt-1 opacity-90"
            >
              ⚡ Running low — top up now
            </motion.p>
          )}
          {activePlan && (
            <div className="mt-3 flex items-center gap-1.5 bg-white/20 rounded-full px-3 py-1 w-fit">
              <CheckCircle2 size={12} />
              <span className="text-[11px] font-semibold capitalize">{activePlan.plan} active</span>
            </div>
          )}
        </div>

        {/* Tab switcher */}
        <div className="flex rounded-[14px] bg-[#E8E8ED] p-1 gap-1">
          {(['monthly', 'packs'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => { hap.select(); setActiveSubTab(tab) }}
              className={`flex-1 py-2 rounded-[10px] text-[13px] font-semibold transition-all ${
                activeSubTab === tab
                  ? 'bg-white text-[#1D1D1F] shadow-sm'
                  : 'text-[#6E6E73]'
              }`}
            >
              {tab === 'monthly' ? '💎 Subscriptions' : '⚡ Credit Packs'}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {activeSubTab === 'monthly' ? (
            <motion.div key="subs"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.15 }}
              className="space-y-3"
            >
              {/* Pro → Creator upgrade nudge — shown when Pro user is running low */}
              {activePlan?.plan === 'pro' && credits <= 15 && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 px-4 py-3 rounded-[14px] bg-gradient-to-r from-[#FF2D78]/10 to-[#FF9500]/10 border border-[#FF2D78]/25"
                >
                  <span className="text-[22px] flex-shrink-0">🔥</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-bold text-[#1D1D1F]">Running low on Pro credits?</p>
                    <p className="text-[11px] text-[#6E6E73]">Creator gives 320⚡/mo — 4× more than Pro</p>
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.96 }}
                    onClick={() => {
                      track('upgrade_nudge_tapped', { from: 'shop_subs', plan: activePlan.plan })
                      setBillingCycle('monthly')
                    }}
                    className="px-3 py-1.5 rounded-[10px] text-white text-[11px] font-bold flex-shrink-0"
                    style={{ background: 'linear-gradient(135deg, #FF2D78, #FF9500)' }}
                  >
                    Upgrade →
                  </motion.button>
                </motion.div>
              )}

              {/* Monthly / Annual billing toggle */}
              {(shop?.annual_subscriptions ?? []).length > 0 && (
                <div className="flex rounded-[12px] bg-[#E8E8ED] p-1 gap-1">
                  {(['monthly', 'annual'] as const).map((cycle) => (
                    <button
                      key={cycle}
                      onClick={() => { hap.select(); setBillingCycle(cycle); track('billing_cycle_switched', { cycle }) }}
                      className={`flex-1 py-1.5 rounded-[8px] text-[12px] font-semibold transition-all flex items-center justify-center gap-1.5 ${
                        billingCycle === cycle ? 'bg-white text-[#1D1D1F] shadow-sm' : 'text-[#6E6E73]'
                      }`}
                    >
                      {cycle === 'monthly' ? 'Monthly' : 'Annual'}
                      {cycle === 'annual' && (
                        <span className="px-1.5 py-0.5 rounded-full bg-[#34C759] text-white text-[9px] font-bold">−20%</span>
                      )}
                    </button>
                  ))}
                </div>
              )}

              {/* Subscription comparison cards */}
              {((billingCycle === 'annual' && (shop?.annual_subscriptions ?? []).length > 0)
                  ? (shop?.annual_subscriptions ?? [])
                  : (shop?.subscriptions ?? [])
              ).map((sub) => {
                const meta = SUB_META[sub.id] ?? { color: '#6C47FF', label: sub.plan, emoji: '⚡' }
                const isActive = activePlan?.plan === sub.plan
                const features = shop?.subscription_features?.[sub.plan] ?? []
                return (
                  <motion.div
                    key={sub.id}
                    whileTap={isActive ? {} : { scale: 0.98 }}
                    className={`rounded-[20px] overflow-hidden border-2 ${
                      isActive ? 'border-[#34C759]' : 'border-black/[0.06]'
                    } bg-white`}
                    style={!isActive && meta.badge ? { borderColor: `${meta.color}66` } : undefined}
                  >
                    {meta.badge && !isActive && (
                      <div className="py-1.5 text-center text-[11px] font-bold text-white"
                        style={{ background: `linear-gradient(90deg, ${meta.color}, #FF2D78)` }}>
                        {meta.badge}
                      </div>
                    )}
                    {isActive && (
                      <div className="py-1.5 text-center text-[11px] font-bold text-white bg-[#34C759]">
                        ✓ Your current plan
                      </div>
                    )}
                    <div className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-[22px]">{meta.emoji}</span>
                          <div>
                            <p className="text-[16px] font-bold text-[#1D1D1F]">{meta.label}</p>
                            <p className="text-[11px] text-[#6E6E73]">{sub.credits} gens / {sub.period}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="flex items-center gap-1">
                            <Star size={13} style={{ color: meta.color }} fill={meta.color} strokeWidth={0} />
                            <span className="text-[18px] font-black" style={{ color: meta.color }}>{sub.stars}</span>
                          </div>
                          <p className="text-[10px] text-[#6E6E73]">per {sub.period}</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-1.5 mb-3">
                        {features.slice(0, 4).map((f) => (
                          <div key={f} className="flex items-center gap-1">
                            <Check size={11} style={{ color: meta.color }} strokeWidth={3} />
                            <span className="text-[11px] text-[#1D1D1F]">{f}</span>
                          </div>
                        ))}
                      </div>
                      {!isActive && (
                        <motion.button
                          whileTap={{ scale: 0.97 }}
                          onClick={() => handleBuy(sub.id, sub.stars)}
                          className="w-full py-3 rounded-[14px] text-white text-[14px] font-bold"
                          style={{ background: `linear-gradient(135deg, ${meta.color}, #FF2D78)` }}
                        >
                          Subscribe · {sub.stars}★ / {sub.period}
                        </motion.button>
                      )}
                      {isActive && activePlan?.expiry && (
                        <p className="text-center text-[11px] text-[#34C759] font-medium">
                          Renews {new Date(activePlan.expiry).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </motion.div>
                )
              })}

              {/* Free vs Pro comparison */}
              <div className="rounded-[20px] bg-white border border-black/[0.06] p-4">
                <p className="text-[13px] font-bold text-[#1D1D1F] mb-3">Free vs Pro</p>
                <div className="grid grid-cols-3 gap-x-2 text-[11px]">
                  <div className="text-[#6E6E73] font-medium">Feature</div>
                  <div className="text-center text-[#6E6E73] font-medium">Free</div>
                  <div className="text-center font-bold" style={{ color: '#6C47FF' }}>Pro</div>
                  {[
                    ['Daily gens', '5', '50+'],
                    ['HD upscale', '✗', '✓'],
                    ['All styles', '✓', '✓'],
                    ['Batch ×4', '✗', '✓'],
                    ['Priority', '✗', '✓'],
                  ].map(([feat, free, pro]) => (
                    <>
                      <div key={feat} className="py-1.5 border-t border-black/[0.04] text-[#1D1D1F]">{feat}</div>
                      <div className={`py-1.5 border-t border-black/[0.04] text-center ${free === '✗' ? 'text-[#FF3B30]' : 'text-[#34C759]'}`}>{free}</div>
                      <div className={`py-1.5 border-t border-black/[0.04] text-center font-bold ${pro === '✗' ? 'text-[#FF3B30]' : 'text-[#6C47FF]'}`}>{pro}</div>
                    </>
                  ))}
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div key="packs"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.15 }}
              className="space-y-4"
            >
              {/* Bundle of the week — shown in-tab only for control variant */}
              {shop?.bundle && bundleVariant !== 'top' && (
                <BundleCard bundle={shop.bundle} onBuy={() => handleBuy(shop!.bundle!.id, shop!.bundle!.stars)} />
              )}

              {/* Credit packs grid */}
              <div className="grid grid-cols-2 gap-3">
                {(shop?.packs ?? []).map((pack) => {
                  const perCredit = Math.round(pack.stars / pack.credits)
                  const meta = PACK_META[pack.id] ?? {}
                  return (
                    <motion.button
                      key={pack.id}
                      whileTap={{ scale: 0.96 }}
                      onClick={() => handleBuy(pack.id, pack.stars)}
                      className={`relative p-4 rounded-[20px] text-left overflow-hidden ${
                        meta.highlight
                          ? 'bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] text-white'
                          : 'bg-white border border-black/[0.06]'
                      }`}
                    >
                      {meta.badge && (
                        <div className={`absolute top-2 right-2 px-2 py-0.5 rounded-full text-[9px] font-bold ${
                          meta.highlight ? 'bg-white/20 text-white' : 'bg-[#6C47FF]/15 text-[#6C47FF]'
                        }`}>
                          {meta.badge}
                        </div>
                      )}
                      <div className="flex items-center gap-1 mb-0.5">
                        <Zap size={15} className={meta.highlight ? 'text-white' : 'text-[#6C47FF]'}
                          fill={meta.highlight ? 'white' : '#6C47FF'} strokeWidth={0} />
                        <span className={`text-[26px] font-black leading-none ${meta.highlight ? 'text-white' : 'text-[#1D1D1F]'}`}>
                          {pack.credits}
                        </span>
                      </div>
                      <p className={`text-[11px] mb-2 ${meta.highlight ? 'text-white/80' : 'text-[#6E6E73]'}`}>
                        generations
                      </p>
                      <p className={`text-[13px] font-bold ${meta.highlight ? 'text-white' : 'text-[#6C47FF]'}`}>
                        {pack.stars}★
                      </p>
                      <p className={`text-[10px] ${meta.highlight ? 'text-white/70' : 'text-[#6E6E73]'}`}>
                        {perCredit}★ per gen
                      </p>
                    </motion.button>
                  )
                })}
              </div>

              {/* Value tip */}
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-[12px] bg-[#6C47FF]/8 border border-[#6C47FF]/15">
                <span className="text-[18px]">💡</span>
                <p className="text-[12px] text-[#1D1D1F]">
                  <span className="font-bold">100-pack saves 40%</span> vs buying 10 at a time
                </p>
              </div>

              {/* Style packs */}
              {(shop?.style_packs ?? []).some((p) => !p.unlocked) && (
                <div>
                  <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2">Style Packs</p>
                  <div className="space-y-2">
                    {(shop?.style_packs ?? []).filter((p) => !p.unlocked).map((pack) => (
                      <motion.button
                        key={pack.id}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => handleBuy(pack.id, pack.stars)}
                        className="w-full flex items-center gap-3 p-4 rounded-[16px] bg-white border border-black/[0.06]"
                      >
                        <div className="w-10 h-10 rounded-[12px] bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] flex items-center justify-center">
                          <Crown size={18} className="text-white" />
                        </div>
                        <div className="flex-1 text-left">
                          <p className="text-[14px] font-semibold text-[#1D1D1F]">{pack.label}</p>
                          <p className="text-[11px] text-[#6E6E73]">{pack.styles_count} exclusive styles · one-time</p>
                        </div>
                        <div className="flex items-center gap-1 text-[#6C47FF] font-bold text-[13px]">
                          <Star size={12} fill="#6C47FF" strokeWidth={0} />
                          {pack.stars}
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </div>
              )}

              {/* Preset packs */}
              {(shop?.preset_packs ?? []).some((p) => !p.unlocked) && (
                <div>
                  <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2">Preset Packs</p>
                  <div className="space-y-2">
                    {(shop?.preset_packs ?? []).filter((p) => !p.unlocked).map((pack) => (
                      <motion.button
                        key={pack.id}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => handleBuy(pack.id, pack.stars)}
                        className="w-full flex items-center gap-3 p-4 rounded-[16px] bg-gradient-to-r from-[#FF9500]/8 to-[#6C47FF]/8 border border-[#FF9500]/20"
                      >
                        <span className="text-[26px]">{pack.emoji}</span>
                        <div className="flex-1 text-left">
                          <p className="text-[14px] font-semibold text-[#1D1D1F]">{pack.label}</p>
                          <p className="text-[11px] text-[#6E6E73]">{pack.presets_count} presets · one-time unlock</p>
                        </div>
                        <span className="text-[13px] font-bold text-[#6C47FF]">{pack.stars}★</span>
                      </motion.button>
                    ))}
                  </div>
                </div>
              )}

              {/* Auto-recharge toggle */}
              <motion.button
                whileTap={{ scale: 0.98 }}
                onClick={handleAutoRechargeToggle}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-[16px] border transition-colors ${
                  autoRechargeEnabled
                    ? 'bg-[#6C47FF]/8 border-[#6C47FF]/30'
                    : 'bg-white border-black/[0.06]'
                }`}
              >
                <RotateCw size={18} className={autoRechargeEnabled ? 'text-[#6C47FF]' : 'text-[#6E6E73]'} />
                <div className="flex-1 text-left">
                  <p className="text-[13px] font-semibold text-[#1D1D1F]">Auto-recharge</p>
                  <p className="text-[11px] text-[#6E6E73]">Get notified when credits drop below 5</p>
                </div>
                <div className={`w-11 h-6 rounded-full transition-colors relative ${autoRechargeEnabled ? 'bg-[#6C47FF]' : 'bg-[#D1D1D6]'}`}>
                  <motion.div
                    animate={{ x: autoRechargeEnabled ? 22 : 2 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                    className="absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm"
                  />
                </div>
              </motion.button>

              {/* Free features */}
              <div className="rounded-[16px] bg-white border border-black/[0.06] p-4">
                <p className="text-[13px] font-bold text-[#1D1D1F] mb-2">✓ Always free</p>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { icon: '🎯', label: 'Batch ×4', sub: '3 credits → 4 photos' },
                    { icon: '💎', label: 'HD Upscale', sub: '+2 credits per photo' },
                    { icon: '🎁', label: 'Daily bonus', sub: '+1 gen every day' },
                    { icon: '👥', label: 'Referrals', sub: '+3 per friend' },
                  ].map(({ icon, label, sub }) => (
                    <div key={label} className="flex items-start gap-2 p-2.5 rounded-[12px] bg-[#F5F5F7]">
                      <span className="text-[16px] mt-0.5">{icon}</span>
                      <div>
                        <p className="text-[12px] font-semibold text-[#1D1D1F]">{label}</p>
                        <p className="text-[10px] text-[#6E6E73]">{sub}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Referral CTA */}
        <motion.button
          whileTap={{ scale: 0.98 }}
          onClick={() => {
            const botBase = user?.bot_link ?? 'https://t.me/imodelapp_bot'
            const refUrl = `${botBase}?start=ref_${user?.uid}`
            const link = `https://t.me/share/url?url=${encodeURIComponent(refUrl)}&text=${encodeURIComponent('AI photo generator! ✨')}`
            tg?.openLink(link)
            track('referral_share_tapped', { source: 'shop' })
          }}
          className="w-full flex items-center gap-3 p-4 rounded-[16px] bg-white border border-black/[0.06]"
        >
          <span className="text-[26px]">🎁</span>
          <div className="flex-1 text-left">
            <p className="text-[14px] font-semibold text-[#1D1D1F]">Invite Friends — Get 3 Free Gens</p>
            <p className="text-[11px] text-[#6E6E73]">They get 3 free gens too · no limit</p>
          </div>
          <ChevronRight size={16} className="text-[#6E6E73]" />
        </motion.button>
      </div>
    </div>
  )
}
