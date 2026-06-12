import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, TrendingUp, Check, X, Heart, Search, Sparkles, Users } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { fetchPresets, getCachedPresets, setCachedPresets } from '../api/presets'
import { createInvoice } from '../api/shop'
import { api } from '../api/client'
import { voteForPreset } from '../api/community'
import { useToast } from '../hooks/useToast'
import { hap } from '../lib/haptics'
import { PresetSkeleton } from '../components/shared/SkeletonLoader'
import type { Preset, Challenge } from '../types'

const CATEGORY_GRADIENT: Record<string, [string, string]> = {
  studio:    ['#1a1a2e', '#16213e'],
  cinematic: ['#1a0a2e', '#2d1533'],
  outdoor:   ['#0d2e1a', '#1a472a'],
  lifestyle: ['#2e1a00', '#3d2600'],
  artistic:  ['#2d0a1a', '#1a0a2e'],
  premium:   ['#0a0a1a', '#1a0030'],
  challenge: ['#1a1000', '#2e2000'],
}

const CATEGORY_ACCENT: Record<string, string> = {
  studio: '#3B82F6',
  cinematic: '#7C3AED',
  outdoor: '#059669',
  lifestyle: '#D97706',
  artistic: '#DB2777',
  premium: '#6C47FF',
  challenge: '#FF9500',
}

const CATEGORIES = ['For You', 'All', 'Studio', 'Cinematic', 'Outdoor', 'Lifestyle', 'Artistic', '★ Premium', '🌍 Community']

function DailyChallengeCard({ challenge, onTap }: { challenge: Challenge; onTap: () => void }) {
  const [timeLeft, setTimeLeft] = useState('')

  useEffect(() => {
    function tick() {
      const now = new Date()
      const end = new Date(now)
      end.setHours(23, 59, 59, 999)
      const diff = end.getTime() - now.getTime()
      const h = Math.floor(diff / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      setTimeLeft(`${h}h ${m}m`)
    }
    tick()
    const id = setInterval(tick, 60000)
    return () => clearInterval(id)
  }, [])

  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      onClick={onTap}
      className="w-full rounded-[18px] overflow-hidden flex items-center gap-3 p-3.5 relative"
      style={{ background: 'linear-gradient(135deg, #1a1000, #2e2000)' }}
    >
      <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(circle at 80% 30%, rgba(255,149,0,0.25) 0%, transparent 60%)' }} />
      <div className="w-12 h-12 rounded-[14px] bg-[#FF9500]/20 border border-[#FF9500]/40 flex items-center justify-center text-[24px] flex-shrink-0 z-10">
        ⚡
      </div>
      <div className="flex-1 text-left z-10">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-[10px] font-bold text-[#FF9500] uppercase tracking-wider">Daily Challenge</span>
          <span className="text-[9px] text-white/40">· {timeLeft} left</span>
        </div>
        <p className="text-[13px] font-bold text-white leading-tight">{challenge.label}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[11px] text-[#FF9500] font-semibold">+{challenge.bonus_credits}⚡ bonus</span>
          {(challenge.participants_today ?? 0) > 0 && (
            <span className="flex items-center gap-0.5 text-[10px] text-white/40">
              <Users size={10} />
              {challenge.participants_today}
            </span>
          )}
        </div>
      </div>
      <div className="z-10">
        <Sparkles size={16} className="text-[#FF9500]/60" />
      </div>
    </motion.button>
  )
}

function PresetCard({ preset, active, index, onTap, onLongPress }: {
  preset: Preset
  active: boolean
  index: number
  onTap: () => void
  onLongPress: () => void
}) {
  const [thumbError, setThumbError] = useState(false)
  const [g1, g2] = CATEGORY_GRADIENT[preset.category] ?? ['#1a1a2e', '#2a2a3e']
  const accent = CATEGORY_ACCENT[preset.category] ?? '#6C47FF'
  const hasThumb = !!preset.thumbnail_url && !thumbError

  let longPressTimer: ReturnType<typeof setTimeout>

  return (
    <motion.button
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.03, type: 'spring', stiffness: 360, damping: 28 }}
      whileTap={{ scale: 0.95 }}
      onClick={onTap}
      onTouchStart={() => { longPressTimer = setTimeout(onLongPress, 480) }}
      onTouchEnd={() => clearTimeout(longPressTimer)}
      onTouchMove={() => clearTimeout(longPressTimer)}
      className="relative rounded-[20px] overflow-hidden flex flex-col"
      style={{
        boxShadow: active
          ? `0 0 0 2.5px ${accent}, 0 4px 24px ${accent}44`
          : '0 2px 12px rgba(0,0,0,0.18)',
      }}
    >
      {/* Thumbnail / gradient placeholder */}
      <div className="aspect-[3/4] relative overflow-hidden">
        {hasThumb ? (
          <img
            src={preset.thumbnail_url}
            alt={preset.label}
            loading="lazy"
            className="w-full h-full object-cover"
            style={preset.locked ? { filter: 'blur(8px)', transform: 'scale(1.1)' } : undefined}
            onError={() => setThumbError(true)}
          />
        ) : (
          <div
            className="w-full h-full relative flex flex-col items-center justify-center gap-2"
            style={{ background: `linear-gradient(160deg, ${g1}, ${g2})` }}
          >
            {/* Bokeh glow circles */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{ background: `radial-gradient(circle at 80% 20%, ${accent}30 0%, transparent 55%)` }}
            />
            <div
              className="absolute inset-0 pointer-events-none"
              style={{ background: `radial-gradient(circle at 20% 75%, ${accent}20 0%, transparent 45%)` }}
            />
            {/* Decorative star */}
            <span
              className="absolute top-2.5 left-2.5 text-[10px] opacity-30 pointer-events-none select-none"
              style={{ color: accent }}
            >
              ✦
            </span>
            {/* Main emoji with glow */}
            <span
              className="text-[52px] drop-shadow-lg relative z-10"
              style={{ filter: `drop-shadow(0 0 14px ${accent}99)` }}
            >
              {preset.emoji}
            </span>
            <span
              className="relative z-10 text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
              style={{ background: `${accent}33`, color: accent }}
            >
              {preset.category}
            </span>
          </div>
        )}

        {/* Bottom label overlay */}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent pt-8 pb-2.5 px-2.5">
          <p className="text-[12px] font-bold text-white leading-tight truncate">{preset.label}</p>
          {!preset.locked && (
            <span
              className="text-[9px] font-semibold uppercase tracking-wide"
              style={{ color: accent }}
            >
              {preset.category}
            </span>
          )}
        </div>

        {/* Lock overlay */}
        {preset.locked && (
          <div className="absolute inset-0 bg-black/35 flex flex-col items-center justify-center gap-1">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center shadow-lg"
              style={{ background: `${accent}55`, border: `1.5px solid ${accent}99` }}
            >
              <Lock size={16} className="text-white" />
            </div>
            <span className="text-[10px] font-bold text-white tracking-wide">Unlock</span>
            <span className="text-[9px] text-white/65">Tap to buy</span>
          </div>
        )}

        {/* Active checkmark */}
        {active && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center"
            style={{ background: accent }}
          >
            <Check size={12} strokeWidth={3} className="text-white" />
          </motion.div>
        )}

        {/* NEW badge */}
        {preset.is_new && !active && (
          <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-bold text-white"
            style={{ background: 'rgba(108,71,255,0.90)' }}>
            NEW
          </div>
        )}

        {/* Usage badge */}
        {(preset.usage_7d ?? 0) > 20 && !preset.locked && (
          <div className="absolute bottom-[52px] right-2 px-1.5 py-0.5 rounded-full text-[9px] font-bold text-white bg-black/50">
            🔥 {preset.usage_7d}
          </div>
        )}
      </div>
    </motion.button>
  )
}

function CommunityCard({ preset, active, index, onTap, onLongPress }: {
  preset: Preset
  active: boolean
  index: number
  onTap: () => void
  onLongPress: () => void
}) {
  const [votes, setVotes] = useState(preset.votes ?? 0)
  const [myVote, setMyVote] = useState(preset.my_vote ?? false)
  const [thumbError, setThumbError] = useState(false)
  const isNew = (preset.created_at ?? 0) > Date.now() / 1000 - 86400
  const isHot = votes >= 10

  let longPressTimer: ReturnType<typeof setTimeout>

  async function handleVote(e: React.MouseEvent) {
    e.stopPropagation()
    hap.light()
    const next = !myVote
    setMyVote(next)
    setVotes((v) => next ? v + 1 : Math.max(0, v - 1))
    try {
      const res = await voteForPreset(preset.key)
      setVotes(res.votes)
      setMyVote(res.my_vote)
    } catch {
      setMyVote(!next)
      setVotes((v) => next ? Math.max(0, v - 1) : v + 1)
    }
  }

  return (
    <motion.button
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.03, type: 'spring', stiffness: 360, damping: 28 }}
      whileTap={{ scale: 0.95 }}
      onClick={onTap}
      onTouchStart={() => { longPressTimer = setTimeout(onLongPress, 480) }}
      onTouchEnd={() => clearTimeout(longPressTimer)}
      onTouchMove={() => clearTimeout(longPressTimer)}
      className="relative rounded-[20px] overflow-hidden flex flex-col"
      style={{
        boxShadow: active
          ? '0 0 0 2.5px #6C47FF, 0 4px 24px #6C47FF44'
          : '0 2px 12px rgba(0,0,0,0.18)',
      }}
    >
      <div className="aspect-[3/4] relative overflow-hidden bg-[#1a1a2e]">
        {preset.thumbnail_url && !thumbError ? (
          <img
            src={preset.thumbnail_url}
            alt={preset.label}
            loading="lazy"
            className="w-full h-full object-cover"
            onError={() => setThumbError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[48px]">✨</div>
        )}

        {/* Hot / New badges */}
        {(isHot || isNew) && (
          <div className="absolute top-2 left-2">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isHot ? 'animate-pulse' : ''}`}
              style={{ background: isHot ? 'rgba(255,80,0,0.85)' : 'rgba(108,71,255,0.85)', color: '#fff' }}>
              {isHot ? '🔥 Hot' : '⭐ New'}
            </span>
          </div>
        )}

        {/* Vote pill */}
        <motion.button
          whileTap={{ scale: 0.85 }}
          onClick={handleVote}
          className="absolute top-2 right-2 flex items-center gap-0.5 px-2 py-1 rounded-full text-[11px] font-bold"
          style={{
            background: myVote ? 'rgba(255,45,120,0.90)' : 'rgba(0,0,0,0.55)',
            color: '#fff',
          }}
        >
          <Heart size={10} fill={myVote ? '#fff' : 'none'} strokeWidth={2.5} />
          <motion.span key={votes} initial={{ scale: 1.4 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500 }}>
            {votes}
          </motion.span>
        </motion.button>

        {/* Bottom: label + creator */}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent pt-8 pb-2.5 px-2.5">
          <p className="text-[12px] font-bold text-white leading-tight truncate">{preset.label}</p>
          <span className="text-[9px] text-white/55">@{preset.creator_name}</span>
        </div>

        {/* Active checkmark */}
        {active && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute top-2 right-10 w-6 h-6 rounded-full flex items-center justify-center bg-[#6C47FF]"
          >
            <Check size={12} strokeWidth={3} className="text-white" />
          </motion.div>
        )}
      </div>
    </motion.button>
  )
}


interface PackPreviewData {
  pack_id: string
  label: string
  emoji: string
  total_presets: number
  stars: number
  previews: { key: string; label: string; emoji: string; thumbnail_url: string }[]
}

function PackPreviewSheet({ packId, onClose, onUnlock }: {
  packId: string
  onClose: () => void
  onUnlock: () => void
}) {
  const [data, setData] = useState<PackPreviewData | null>(null)
  const [loadErr, setLoadErr] = useState(false)

  useEffect(() => {
    api.get<PackPreviewData>(`/api/v1/packs/${packId}/preview`)
      .then(setData)
      .catch(() => setLoadErr(true))
  }, [packId])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[150] bg-black/70 flex items-end"
      style={{ maxWidth: 480, margin: '0 auto' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 80, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
        className="w-full bg-[#1C1C1E] rounded-t-[28px] pb-8 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>

        {loadErr ? (
          <div className="flex flex-col items-center gap-3 py-10 px-5">
            <p className="text-white/50 text-[14px]">Could not load pack preview</p>
            <button onClick={onClose} className="px-6 py-2.5 rounded-[14px] bg-white/10 text-white/70 text-[14px]">Close</button>
          </div>
        ) : !data ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-[#6C47FF] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="px-5">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-[36px]">{data.emoji}</span>
              <div>
                <h3 className="text-[18px] font-bold text-white">{data.label}</h3>
                <span className="text-[13px] text-white/50">{data.total_presets} styles included</span>
              </div>
            </div>

            {/* 2×2 preview grid */}
            <div className="grid grid-cols-4 gap-2 mb-4">
              {data.previews.map((p) => (
                <div key={p.key} className="aspect-[3/4] rounded-[12px] overflow-hidden bg-[#2C2C2E] flex items-center justify-center">
                  {p.thumbnail_url ? (
                    <img src={p.thumbnail_url} alt={p.label} className="w-full h-full object-cover" style={{ filter: 'blur(6px)', transform: 'scale(1.15)' }} />
                  ) : (
                    <span className="text-[24px]">{p.emoji}</span>
                  )}
                </div>
              ))}
              <div className="aspect-[3/4] rounded-[12px] bg-[#2C2C2E] flex items-center justify-center">
                <span className="text-white/30 text-[12px] font-bold">+{Math.max(0, data.total_presets - 4)}</span>
              </div>
            </div>

            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={onUnlock}
              className="w-full py-3.5 rounded-[16px] text-white text-[15px] font-bold bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] flex items-center justify-center gap-2"
            >
              <Sparkles size={16} />
              Unlock Pack · {data.stars}★
            </motion.button>
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

function PreviewModal({ preset, onClose, onSelect }: {
  preset: Preset
  onClose: () => void
  onSelect: () => void
}) {
  const accent = CATEGORY_ACCENT[preset.category] ?? '#6C47FF'
  const [g1, g2] = CATEGORY_GRADIENT[preset.category] ?? ['#1a1a2e', '#2a2a3e']

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[150] bg-black/70 flex items-end"
      style={{ maxWidth: 480, margin: '0 auto' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 80, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
        className="w-full bg-[#1C1C1E] rounded-t-[28px] pb-8 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>

        {/* Large preview */}
        <div className="mx-4 rounded-[20px] overflow-hidden mb-4" style={{ aspectRatio: '3/4' }}>
          {preset.thumbnail_url ? (
            <img src={preset.thumbnail_url} alt={preset.label} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center"
              style={{ background: `linear-gradient(160deg, ${g1}, ${g2})` }}>
              <span className="text-[72px]">{preset.emoji}</span>
            </div>
          )}
        </div>

        <div className="px-5">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[24px]">{preset.emoji}</span>
            <div>
              <h3 className="text-[18px] font-bold text-white">{preset.label}</h3>
              {preset.category === 'community' ? (
                <span className="text-[12px] text-white/50">by @{preset.creator_name} · ❤️ {preset.votes ?? 0}</span>
              ) : (
                <span className="text-[12px] font-semibold" style={{ color: accent }}>{preset.category}</span>
              )}
            </div>
          </div>
          {preset.prompt && (
            <p className="text-[12px] text-white/50 leading-relaxed mb-4 line-clamp-2">{preset.prompt}</p>
          )}
          {preset.locked ? (
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={onSelect}
              className="w-full py-3.5 rounded-[16px] text-white text-[15px] font-bold"
              style={{ background: `linear-gradient(135deg, ${accent}, #FF2D78)` }}
            >
              🔓 Unlock Style
            </motion.button>
          ) : (
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={onSelect}
              className="w-full py-3.5 rounded-[16px] bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[15px] font-bold"
            >
              ✨ Use This Style
            </motion.button>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default function Styles() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('All')
  const [preview, setPreview] = useState<Preset | null>(null)
  const [search, setSearch] = useState('')
  const [packPreview, setPackPreview] = useState<string | null>(null)
  const activePreset = useAppStore((s) => s.activePreset)
  const setActivePreset = useAppStore((s) => s.setActivePreset)
  const setTab = useAppStore((s) => s.setTab)
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const challenge = useAppStore((s) => s.challenge)
  const toast = useToast()

  useEffect(() => {
    const cached = getCachedPresets()
    if (cached) { setPresets(cached); setLoading(false); return }
    fetchPresets()
      .then(({ presets }) => { setPresets(presets); setCachedPresets(presets) })
      .catch(() => toast.error('Failed to load styles'))
      .finally(() => setLoading(false))
  }, [])

  const _recentKeys = new Set(user?.recent_presets ?? [])
  const filtered = category === 'For You'
    ? [...presets]
        .filter((p) => !p.locked)
        .sort((a, b) => {
          // Recently used first, then by personalized_score, then usage_7d
          const aRecent = _recentKeys.has(a.key) ? 1000 : 0
          const bRecent = _recentKeys.has(b.key) ? 1000 : 0
          const aScore = (aRecent + (a.personalized_score ?? 0) + (a.usage_7d ?? 0))
          const bScore = (bRecent + (b.personalized_score ?? 0) + (b.usage_7d ?? 0))
          return bScore - aScore
        })
        .slice(0, 30)
    : category === 'All'
    ? presets.filter((p) => p.category !== 'community')
    : category === '★ Premium'
    ? presets.filter((p) => p.is_premium)
    : category === '🌍 Community'
    ? presets.filter((p) => p.category === 'community')
    : presets.filter((p) => p.category.toLowerCase() === category.toLowerCase())

  const q = search.trim().toLowerCase()
  const displayed = q
    ? presets.filter((p) => p.label.toLowerCase().includes(q) || p.category.toLowerCase().includes(q))
    : filtered

  // Sort by real usage_7d if available, fallback to first 6 free presets
  const trending = [...presets]
    .filter((p) => !p.is_premium && !p.locked)
    .sort((a, b) => ((b as Preset & { usage_7d?: number }).usage_7d ?? 0) - ((a as Preset & { usage_7d?: number }).usage_7d ?? 0))
    .slice(0, 8)

  async function handleUnlockPack(packId: string) {
    hap.medium()
    try {
      const { invoice_url } = await createInvoice(packId)
      tg?.openInvoice(invoice_url, (status: string) => {
        if (status === 'paid' && user) {
          setUser({ ...user, unlocked_packs: [...(user.unlocked_packs ?? []), packId] })
          toast.success('Style pack unlocked!', { icon: '🎉' })
        }
      })
    } catch { toast.error('Could not open payment') }
    setPackPreview(null)
    setPreview(null)
  }

  async function handlePreset(preset: Preset) {
    if (preset.locked && preset.pack_id) {
      hap.medium()
      setPreview(null)
      setPackPreview(preset.pack_id)
      return
    }
    hap.light()
    setActivePreset(preset)
    setTab('studio')
    setPreview(null)
  }

  const tg = window.Telegram?.WebApp

  return (
    <div className="flex flex-col h-full bg-[#F5F5F7]">
      <div className="px-4 pt-4 pb-2">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🎭 Styles</h1>
        <p className="text-[13px] text-[#6E6E73]">Tap to apply · hold to preview</p>

        {/* Search input */}
        <div className="mt-2.5 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8E8E93] pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search styles…"
            className="w-full pl-8 pr-3 py-2 rounded-[12px] bg-[#E8E8ED] text-[13px] text-[#1D1D1F] placeholder-[#8E8E93] outline-none"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X size={12} className="text-[#8E8E93]" />
            </button>
          )}
        </div>
      </div>

      {/* Daily challenge card */}
      {challenge && !search && (
        <div className="mx-4 mb-2">
          <DailyChallengeCard challenge={challenge} onTap={() => {
            const p = presets.find(pr => pr.key === challenge.preset_key)
            if (p) { hap.medium(); setActivePreset(p); setTab('studio') }
          }} />
        </div>
      )}

      {/* Trending row */}
      {trending.length > 0 && (
        <div className="px-4 mb-2 mt-1">
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingUp size={13} className="text-[#FF2D78]" />
            <span className="text-[12px] font-semibold text-[#1D1D1F]">Trending</span>
          </div>
          <div className="flex gap-2.5 overflow-x-auto pb-1 no-scrollbar">
            {trending.map((p) => {
              const [g1, g2] = CATEGORY_GRADIENT[p.category] ?? ['#1a1a2e', '#2a2a3e']
              const isActive = activePreset?.key === p.key
              const usage = (p as Preset & { usage_7d?: number }).usage_7d ?? 0
              return (
                <motion.button
                  key={p.key}
                  whileTap={{ scale: 0.93 }}
                  onClick={() => handlePreset(p)}
                  className="flex-shrink-0 flex flex-col items-center gap-1.5"
                >
                  <div
                    className="w-[68px] h-[68px] rounded-[18px] flex items-center justify-center text-[26px] relative overflow-hidden"
                    style={{
                      background: p.thumbnail_url ? undefined : `linear-gradient(135deg, ${g1}, ${g2})`,
                      outline: isActive ? `2px solid ${CATEGORY_ACCENT[p.category] ?? '#6C47FF'}` : 'none',
                      outlineOffset: '2px',
                    }}
                  >
                    {p.thumbnail_url
                      ? <img src={p.thumbnail_url} alt={p.label} className="w-full h-full object-cover" />
                      : <span>{p.emoji}</span>
                    }
                    {isActive && (
                      <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
                        <Check size={16} strokeWidth={3} className="text-white" />
                      </div>
                    )}
                    {usage > 50 && !isActive && (
                      <div className="absolute bottom-0 left-0 right-0 bg-[#FF2D78] text-white text-[8px] font-bold text-center py-0.5">
                        🔥 {usage}
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-[#1D1D1F] font-medium text-center line-clamp-1 w-[68px]">{p.label}</span>
                </motion.button>
              )
            })}
          </div>
        </div>
      )}

      {/* Category filter */}
      <div className="flex gap-2 overflow-x-auto px-4 pb-2 no-scrollbar">
        {CATEGORIES.map((cat) => (
          <motion.button
            key={cat}
            whileTap={{ scale: 0.95 }}
            onClick={() => { hap.select(); setCategory(cat) }}
            className={`flex-shrink-0 px-3.5 py-1.5 rounded-full text-[12px] font-semibold transition-colors ${
              category === cat
                ? 'bg-[#6C47FF] text-white'
                : 'bg-[#E8E8ED] text-[#6E6E73]'
            }`}
          >
            {cat}
          </motion.button>
        ))}
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto px-4">
        {loading ? (
          <div className="grid grid-cols-2 gap-3 pb-4">
            {Array.from({ length: 8 }).map((_, i) => <PresetSkeleton key={i} />)}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 pb-4">
            {displayed.map((preset, i) =>
              preset.category === 'community' ? (
                <CommunityCard
                  key={preset.key}
                  preset={preset}
                  active={activePreset?.key === preset.key}
                  index={i}
                  onTap={() => handlePreset(preset)}
                  onLongPress={() => { hap.medium(); setPreview(preset) }}
                />
              ) : (
              <PresetCard
                key={preset.key}
                preset={preset}
                active={activePreset?.key === preset.key}
                index={i}
                onTap={() => handlePreset(preset)}
                onLongPress={() => { hap.medium(); setPreview(preset) }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Preview modal */}
      <AnimatePresence>
        {preview && (
          <PreviewModal
            preset={preview}
            onClose={() => setPreview(null)}
            onSelect={() => handlePreset(preview)}
          />
        )}
        {packPreview && (
          <PackPreviewSheet
            packId={packPreview}
            onClose={() => setPackPreview(null)}
            onUnlock={() => handleUnlockPack(packPreview)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
