import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Lock, TrendingUp } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { fetchPresets, getCachedPresets, setCachedPresets } from '../api/presets'
import { createInvoice } from '../api/shop'
import type { Preset } from '../types'

const tg = window.Telegram?.WebApp

const CATEGORY_COLORS: Record<string, string> = {
  studio: '#3B82F6',
  cinematic: '#7C3AED',
  outdoor: '#059669',
  lifestyle: '#D97706',
  artistic: '#DB2777',
  premium: '#6C47FF',
  challenge: '#FF9500',
}

const CATEGORIES = ['All', 'Studio', 'Cinematic', 'Outdoor', 'Lifestyle', 'Artistic', '★ Premium']

export default function Styles() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [category, setCategory] = useState('All')
  const setActivePreset = useAppStore((s) => s.setActivePreset)
  const setTab = useAppStore((s) => s.setTab)
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)

  useEffect(() => {
    const cached = getCachedPresets()
    if (cached) { setPresets(cached); return }
    fetchPresets().then(({ presets }) => {
      setPresets(presets)
      setCachedPresets(presets)
    })
  }, [])

  const filtered = category === 'All'
    ? presets
    : category === '★ Premium'
    ? presets.filter((p) => p.is_premium)
    : presets.filter((p) => p.category.toLowerCase() === category.toLowerCase())

  const trending = presets.filter((p) => !p.is_premium).slice(0, 5)

  async function handlePreset(preset: Preset) {
    if (preset.locked && preset.pack_id) {
      tg?.HapticFeedback?.impactOccurred('medium')
      try {
        const { invoice_url } = await createInvoice(preset.pack_id)
        tg?.openInvoice(invoice_url, (status: string) => {
          if (status === 'paid' && user) {
            setUser({ ...user, unlocked_packs: [...(user.unlocked_packs ?? []), preset.pack_id!] })
          }
        })
      } catch { /* noop */ }
      return
    }
    tg?.HapticFeedback?.impactOccurred('light')
    setActivePreset(preset)
    setTab('studio')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-2">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🎭 Styles</h1>
      </div>

      {/* Trending row */}
      {trending.length > 0 && (
        <div className="px-4 mb-3">
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingUp size={14} className="text-[#FF2D78]" />
            <span className="text-[12px] font-semibold text-[#1D1D1F]">Trending This Week</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
            {trending.map((p) => (
              <motion.button
                key={p.key}
                whileTap={{ scale: 0.95 }}
                onClick={() => handlePreset(p)}
                className="flex-shrink-0 w-20 flex flex-col items-center gap-1.5"
              >
                <div
                  className="w-20 h-20 rounded-card flex items-center justify-center text-3xl"
                  style={{ background: `linear-gradient(135deg, ${CATEGORY_COLORS[p.category] ?? '#6C47FF'}33, ${CATEGORY_COLORS[p.category] ?? '#6C47FF'}66)` }}
                >
                  {p.emoji}
                </div>
                <span className="text-[10px] text-[#1D1D1F] font-medium text-center line-clamp-1">{p.label}</span>
              </motion.button>
            ))}
          </div>
        </div>
      )}

      {/* Category filter */}
      <div className="flex gap-2 overflow-x-auto px-4 pb-2 no-scrollbar">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => { tg?.HapticFeedback?.selectionChanged(); setCategory(cat) }}
            className={`flex-shrink-0 px-3 py-1.5 rounded-pill text-[12px] font-medium transition-colors ${
              category === cat
                ? 'bg-[#6C47FF] text-white'
                : 'bg-[#F5F5F7] text-[#6E6E73]'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Style Pack Banner */}
      {user && !(user.unlocked_packs ?? []).includes('premium_pack_1') && (
        <div className="mx-4 mb-3">
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={async () => {
              try {
                const { invoice_url } = await createInvoice('premium_pack_1')
                tg?.openInvoice(invoice_url, (status: string) => {
                  if (status === 'paid' && user) {
                    setUser({ ...user, unlocked_packs: [...(user.unlocked_packs ?? []), 'premium_pack_1'] })
                  }
                })
              } catch { /* noop */ }
            }}
            className="w-full p-4 rounded-card bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[15px] font-bold">★ Premium Style Pack</p>
                <p className="text-[12px] opacity-80">15 exclusive styles · Unlock once</p>
              </div>
              <div className="text-right">
                <p className="text-[18px] font-bold">490 ★</p>
              </div>
            </div>
          </motion.button>
        </div>
      )}

      {/* Grid */}
      <div className="flex-1 overflow-y-auto px-4">
        <div className="grid grid-cols-3 gap-2.5 pb-4">
          {filtered.map((preset, i) => {
            const color = CATEGORY_COLORS[preset.category] ?? '#6C47FF'
            return (
              <motion.button
                key={preset.key}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => handlePreset(preset)}
                className="relative flex flex-col rounded-card overflow-hidden"
                style={{ background: `linear-gradient(135deg, ${color}22, ${color}44)` }}
              >
                <div className="aspect-square flex items-center justify-center text-[32px]">
                  {preset.emoji}
                </div>
                <div className="px-2 pb-2">
                  <p className="text-[11px] font-semibold text-[#1D1D1F] truncate">{preset.label}</p>
                </div>
                {preset.locked && (
                  <div className="absolute inset-0 bg-black/40 backdrop-blur-sm flex flex-col items-center justify-center gap-1">
                    <Lock size={16} className="text-white" />
                    <span className="text-[10px] text-white font-semibold">Unlock</span>
                  </div>
                )}
              </motion.button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
