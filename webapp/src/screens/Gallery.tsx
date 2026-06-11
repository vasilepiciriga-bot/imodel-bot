import { useEffect, useState, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, Download, RefreshCw, Star, Images, Trophy, Share2,
  Pencil, Copy, Check, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { getGallery, getCachedGallery, setCachedGallery, requestHD } from '../api/generations'
import { getLeaderboard, type LeaderboardData } from '../api/leaderboard'
import { setPortfolioVisibility } from '../api/portfolio'
import { getMe } from '../api/session'
import { generateCaption } from '../api/caption'
import { reactToPhoto } from '../api/quests'
import { track } from '../api/analytics'
import { useToast } from '../hooks/useToast'
import type { Generation } from '../types'

const EMOJIS = ['❤️', '🔥', '😍', '👏', '😮']

interface ReactionState {
  counts: Record<string, number>
  mine: string | null
}

function ReactionRow({ jobId, state, compact, onReact }: {
  jobId: string
  state: ReactionState
  compact: boolean
  onReact: (jobId: string, emoji: string) => void
}) {
  const total = Object.values(state.counts).reduce((s, n) => s + n, 0)
  if (compact) {
    return (
      <div className="flex items-center gap-1 flex-wrap" onClick={(e) => e.stopPropagation()}>
        {EMOJIS.slice(0, 3).map((em) => {
          const n = state.counts[em] ?? 0
          const active = state.mine === em
          return (
            <motion.button
              key={em}
              whileTap={{ scale: 0.85 }}
              onClick={() => onReact(jobId, em)}
              className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                active
                  ? 'bg-[#6C47FF] text-white'
                  : n > 0 ? 'bg-black/40 text-white' : 'bg-black/20 text-white/60'
              }`}
            >
              <span>{em}</span>
              {n > 0 && <span>{n}</span>}
            </motion.button>
          )
        })}
        {total === 0 && <span className="text-[9px] text-white/40">Tap to react</span>}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
      {EMOJIS.map((em) => {
        const n = state.counts[em] ?? 0
        const active = state.mine === em
        return (
          <motion.button
            key={em}
            whileTap={{ scale: 0.85 }}
            onClick={() => onReact(jobId, em)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-[13px] font-medium transition-colors ${
              active
                ? 'bg-[#6C47FF] text-white'
                : 'bg-white/10 text-white'
            }`}
          >
            <span>{em}</span>
            {n > 0 && <span className="text-[12px]">{n}</span>}
          </motion.button>
        )
      })}
    </div>
  )
}

const tg = window.Telegram?.WebApp

const MEDALS = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

function LeaderboardModal({ data, onClose }: { data: LeaderboardData; onClose: () => void }) {
  const period = data.period === '7d' ? 'This week' : 'All time'
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col bg-black/80"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', stiffness: 320, damping: 32 }}
        className="mt-auto bg-[#1C1C1E] rounded-t-[24px] pb-safe"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-8 h-1 bg-white/20 rounded-full" />
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div>
            <h2 className="text-[17px] font-bold text-white">🏆 Leaderboard</h2>
            <p className="text-[12px] text-white/50 mt-0.5">{period} · top generators</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
            <X size={16} className="text-white/70" />
          </button>
        </div>
        <div className="px-4 py-3 space-y-1 max-h-[60vh] overflow-y-auto">
          {data.entries.map((e) => (
            <motion.div
              key={e.rank}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: e.rank * 0.04 }}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-[12px] ${
                e.is_me ? 'bg-[#6C47FF]/20 border border-[#6C47FF]/40' : 'bg-white/5'
              }`}
            >
              <span className="text-[20px] w-7 text-center">{MEDALS[e.rank - 1] ?? `#${e.rank}`}</span>
              <span className={`flex-1 text-[14px] font-medium ${e.is_me ? 'text-[#A88FFF]' : 'text-white'}`}>
                {e.display_name}{e.is_me ? ' · you' : ''}
              </span>
              <span className="text-[13px] text-white/60 font-semibold">{e.gens}⚡</span>
            </motion.div>
          ))}
          {data.my_rank && data.my_rank > 10 && (
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-[12px] bg-[#6C47FF]/10 border border-[#6C47FF]/20 mt-3">
              <span className="text-[20px] w-7 text-center">#{data.my_rank}</span>
              <span className="flex-1 text-[14px] font-medium text-[#A88FFF]">You</span>
              <span className="text-[13px] text-white/60 font-semibold">{data.my_gens}⚡</span>
            </div>
          )}
        </div>
        <div className="px-4 pb-4 pt-2">
          <p className="text-[11px] text-white/30 text-center">Generate more photos to climb the ranks ✦</p>
        </div>
      </motion.div>
    </motion.div>
  )
}

function CaptionSheet({ captions, onClose, onRegenerate, loading }: {
  captions: string[]
  onClose: () => void
  onRegenerate: () => void
  loading: boolean
}) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)

  function copyCaption(text: string, idx: number) {
    navigator.clipboard.writeText(text).catch(() => null)
    tg?.HapticFeedback?.notificationOccurred('success')
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[60] flex flex-col bg-black/60"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', stiffness: 320, damping: 32 }}
        className="mt-auto bg-[#1C1C1E] rounded-t-[24px] pb-safe"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-8 h-1 bg-white/20 rounded-full" />
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div>
            <h2 className="text-[17px] font-bold text-white">📝 Caption Ideas</h2>
            <p className="text-[12px] text-white/50 mt-0.5">Tap to copy · ready for IG & TikTok</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
            <X size={16} className="text-white/70" />
          </button>
        </div>
        <div className="px-4 py-3 space-y-2">
          {loading ? (
            <div className="flex items-center justify-center py-8 gap-3">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full"
              />
              <span className="text-[13px] text-white/60">Writing captions…</span>
            </div>
          ) : (
            captions.map((cap, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06 }}
                className="flex items-start gap-3 p-3 rounded-[14px] bg-white/8"
              >
                <p className="flex-1 text-[13px] text-white/90 leading-relaxed">{cap}</p>
                <button
                  onClick={() => copyCaption(cap, i)}
                  className="shrink-0 w-8 h-8 rounded-full bg-white/10 flex items-center justify-center mt-0.5"
                >
                  {copiedIdx === i
                    ? <Check size={13} className="text-[#34C759]" />
                    : <Copy size={13} className="text-white/60" />
                  }
                </button>
              </motion.div>
            ))
          )}
        </div>
        <div className="px-4 pb-5 pt-1">
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={onRegenerate}
            disabled={loading}
            className="w-full py-3 rounded-[14px] bg-[#6C47FF]/20 text-[#A88FFF] text-[14px] font-semibold disabled:opacity-40"
          >
            {loading ? 'Regenerating…' : '✨ Regenerate captions'}
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ─── Day grouping helpers ──────────────────────────────────────────────────────

function dayLabel(ts: number): string {
  if (!ts) return 'Earlier'
  const d = new Date(ts * 1000)
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === now.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en', { month: 'long', day: 'numeric' })
}

function groupByDay(items: Generation[]): { label: string; items: Generation[] }[] {
  const map = new Map<string, Generation[]>()
  for (const item of items) {
    const label = dayLabel(Number(item.created_at))
    if (!map.has(label)) map.set(label, [])
    map.get(label)!.push(item)
  }
  return Array.from(map.entries()).map(([label, items]) => ({ label, items }))
}

// ─── Slide animation variants ──────────────────────────────────────────────────

const slideVariants = {
  enter: (d: number) => ({
    x: d > 0 ? '65%' : d < 0 ? '-65%' : 0,
    opacity: d !== 0 ? 0.6 : 1,
  }),
  center: { x: 0, opacity: 1 },
  exit: (d: number) => ({
    x: d > 0 ? '-65%' : d < 0 ? '65%' : 0,
    opacity: d !== 0 ? 0.6 : 1,
  }),
}

// ─── Main Gallery screen ───────────────────────────────────────────────────────

export default function Gallery() {
  const gallery = useAppStore((s) => s.gallery)
  const setGallery = useAppStore((s) => s.setGallery)
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)

  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [swipeDir, setSwipeDir] = useState(0)
  const [hdLoading, setHdLoading] = useState(false)
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null)
  const [showLeaderboard, setShowLeaderboard] = useState(false)
  const [portfolioLoading, setPortfolioLoading] = useState(false)
  const [captions, setCaptions] = useState<string[]>([])
  const [captionLoading, setCaptionLoading] = useState(false)
  const [showCaptions, setShowCaptions] = useState(false)
  const [reactions, setReactions] = useState<Record<string, ReactionState>>({})
  const toast = useToast()

  // Sort newest first
  const sorted = useMemo(
    () =>
      [...gallery].sort((a, b) => {
        const ta = a.created_at ? Number(a.created_at) : 0
        const tb = b.created_at ? Number(b.created_at) : 0
        return tb - ta
      }),
    [gallery]
  )
  const groups = useMemo(() => groupByDay(sorted), [sorted])
  const lightbox = lightboxIndex !== null ? sorted[lightboxIndex] : null

  useEffect(() => {
    const cached = getCachedGallery()
    if (cached?.length) { setGallery(cached); return }
    getGallery().then(({ items }) => {
      setGallery(items)
      setCachedGallery(items)
    }).catch(() => null)
  }, [setGallery])

  useEffect(() => {
    getLeaderboard().then(setLeaderboard).catch(() => null)
  }, [])

  function openLightbox(item: Generation) {
    tg?.HapticFeedback?.impactOccurred('light')
    const idx = sorted.findIndex((s) => s.job_id === item.job_id)
    setSwipeDir(0)
    setLightboxIndex(idx >= 0 ? idx : null)
  }

  function navigate(dir: number) {
    if (lightboxIndex === null) return
    const next = lightboxIndex + dir
    if (next < 0 || next >= sorted.length) return
    setSwipeDir(dir)
    tg?.HapticFeedback?.impactOccurred('light')
    setLightboxIndex(next)
  }

  async function handleReact(jobId: string, emoji: string) {
    tg?.HapticFeedback?.impactOccurred('light')
    setReactions((prev) => {
      const cur = prev[jobId] ?? { counts: {}, mine: null }
      const counts = { ...cur.counts }
      if (cur.mine) counts[cur.mine] = Math.max(0, (counts[cur.mine] ?? 1) - 1)
      const isToggle = cur.mine === emoji
      if (!isToggle) counts[emoji] = (counts[emoji] ?? 0) + 1
      return { ...prev, [jobId]: { counts, mine: isToggle ? null : emoji } }
    })
    try {
      const res = await reactToPhoto(jobId, emoji)
      setReactions((prev) => ({ ...prev, [jobId]: { counts: res.reactions, mine: res.my_reaction } }))
    } catch { /* optimistic stays */ }
  }

  async function handleHD(job: Generation) {
    setHdLoading(true)
    try {
      await requestHD(job.job_id)
      tg?.HapticFeedback?.notificationOccurred('success')
      toast.success('HD upgrade started!', { sub: 'Ready in ~30 seconds' })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'HD upgrade failed'
      toast.error(msg)
    } finally {
      setHdLoading(false)
    }
  }

  async function handleCaption(job: Generation) {
    tg?.HapticFeedback?.impactOccurred('light')
    setShowCaptions(true)
    setCaptionLoading(true)
    const style = job.preset_key ?? job.photoshoot_mode ?? job.mode ?? 'portrait'
    const mode = job.photoshoot_mode ?? job.mode ?? 'portrait'
    try {
      const { captions: caps } = await generateCaption(style, mode)
      setCaptions(caps)
      track('caption_viewed', { style, mode })
    } catch {
      setCaptions(['Could not generate captions. Try again.'])
    } finally {
      setCaptionLoading(false)
    }
  }

  async function regenerateCaption(job: Generation) {
    setCaptionLoading(true)
    const style = job.preset_key ?? job.photoshoot_mode ?? job.mode ?? 'portrait'
    const mode = job.photoshoot_mode ?? job.mode ?? 'portrait'
    try {
      const { captions: caps } = await generateCaption(style, mode)
      setCaptions(caps)
      track('caption_regenerated', { style })
    } catch { /* noop */ } finally {
      setCaptionLoading(false)
    }
  }

  function openLeaderboard() {
    tg?.HapticFeedback?.impactOccurred('light')
    setShowLeaderboard(true)
    track('leaderboard_viewed', { source: 'webapp' })
  }

  async function handleSharePortfolio() {
    tg?.HapticFeedback?.impactOccurred('medium')
    setPortfolioLoading(true)
    try {
      let url = user?.portfolio_url ?? null
      if (!user?.portfolio_public) {
        const res = await setPortfolioVisibility(true)
        url = res.portfolio_url
        const updated = await getMe()
        setUser(updated)
      }
      if (!url) return
      track('portfolio_shared', { source: 'gallery' })
      const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent('Check out my AI portraits! ✨')}`
      tg?.openLink(shareUrl)
    } catch { /* noop */ } finally {
      setPortfolioLoading(false)
    }
  }

  const top3 = leaderboard?.entries.slice(0, 3) ?? []

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🖼 Gallery</h1>
        <div className="flex items-center gap-2">
          {gallery.length > 0 && (
            <span className="text-[13px] text-[#6E6E73]">{gallery.length} photos</span>
          )}
          {gallery.length > 0 && (
            <motion.button
              whileTap={{ scale: 0.92 }}
              onClick={handleSharePortfolio}
              disabled={portfolioLoading}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#6C47FF]/15 border border-[#6C47FF]/30"
            >
              <Share2 size={12} className="text-[#6C47FF]" />
              <span className="text-[11px] font-semibold text-[#6C47FF]">
                {user?.portfolio_public ? 'Share' : 'Portfolio'}
              </span>
            </motion.button>
          )}
          {leaderboard && (
            <motion.button
              whileTap={{ scale: 0.92 }}
              onClick={openLeaderboard}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#FFD700]/15 border border-[#FFD700]/30"
            >
              <Trophy size={12} className="text-[#B8860B]" />
              <span className="text-[11px] font-semibold text-[#B8860B]">Top</span>
            </motion.button>
          )}
        </div>
      </div>

      {/* Leaderboard strip */}
      {leaderboard && top3.length > 0 && gallery.length > 0 && (
        <motion.button
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          whileTap={{ scale: 0.98 }}
          onClick={openLeaderboard}
          className="mx-4 mb-3 flex items-center gap-0 px-3 py-2.5 rounded-[14px] bg-gradient-to-r from-[#FFD700]/10 to-[#6C47FF]/10 border border-[#FFD700]/20"
        >
          <div className="flex items-center gap-1 flex-1">
            {top3.map((e, i) => (
              <span key={i} className="text-[13px]">{MEDALS[i]}</span>
            ))}
            <span className="text-[12px] text-[#1D1D1F] font-medium ml-1.5">
              {top3[0]?.display_name} leads with {top3[0]?.gens} gens
            </span>
          </div>
          {leaderboard.my_rank && (
            <span className="text-[11px] text-[#6E6E73] ml-2 shrink-0">
              You #{leaderboard.my_rank}
            </span>
          )}
        </motion.button>
      )}

      {gallery.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-8 text-center">
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#6C47FF]/20 to-[#FF2D78]/20 flex items-center justify-center">
            <Images size={32} className="text-[#6C47FF]" />
          </div>
          <div>
            <p className="text-[17px] font-semibold text-[#1D1D1F]">No photos yet</p>
            <p className="text-[14px] text-[#6E6E73] mt-1">Generate your first AI photo in Studio</p>
          </div>
          {leaderboard && top3.length > 0 && (
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={openLeaderboard}
              className="mt-2 px-4 py-2 rounded-full bg-[#FFD700]/15 border border-[#FFD700]/30 text-[13px] font-medium text-[#B8860B]"
            >
              🏆 See who's winning this week
            </motion.button>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4">
          {groups.map(({ label, items: dayItems }) => (
            <div key={label} className="mb-4">
              <p className="text-[11px] font-semibold text-[#6E6E73] uppercase tracking-wider py-2 sticky top-0 bg-[#F5F5F7] z-10">
                {label}
              </p>
              <div className="columns-2 gap-2.5">
                {dayItems.map((item, i) => (
                  <motion.div
                    key={item.job_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(i * 0.04, 0.4) }}
                    className="break-inside-avoid mb-2.5 relative"
                  >
                    <div
                      className="relative"
                      onClick={() => openLightbox(item)}
                    >
                      <img
                        src={item.hd_url ?? item.output_url}
                        alt={item.preset_key ?? 'photo'}
                        loading="lazy"
                        className="w-full rounded-t-card object-cover"
                      />
                      {item.hd_url && (
                        <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] rounded-full text-[9px] text-white font-bold">
                          HD
                        </div>
                      )}
                      <div className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 bg-black/50 rounded-full text-[9px] text-white truncate max-w-[80%]">
                        {item.preset_key ?? item.mode ?? 'portrait'}
                      </div>
                    </div>
                    <div className="px-1.5 py-1.5 bg-white rounded-b-card border border-black/[0.05]">
                      <ReactionRow
                        jobId={item.job_id}
                        state={reactions[item.job_id] ?? { counts: {}, mine: null }}
                        compact
                        onReact={handleReact}
                      />
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          ))}
          <div className="pb-4" />
        </div>
      )}

      {createPortal(<>
      {/* Lightbox */}
      <AnimatePresence>
        {lightbox && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/92 flex flex-col"
            onClick={() => setLightboxIndex(null)}
          >
            {/* Header: counter + close */}
            <div
              className="flex items-center justify-between px-4 pb-3"
              style={{ paddingTop: 'calc(var(--tg-safe-top, env(safe-area-inset-top, 0px)) + 12px)' }}
            >
              <span className="text-white/55 text-[13px] font-medium tabular-nums">
                {(lightboxIndex ?? 0) + 1} / {sorted.length}
              </span>
              <button onClick={() => setLightboxIndex(null)}>
                <X size={24} className="text-white" />
              </button>
            </div>

            {/* Swipeable image area */}
            <div
              className="flex-1 relative overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              <AnimatePresence custom={swipeDir} mode="wait">
                <motion.div
                  key={lightbox.job_id}
                  custom={swipeDir}
                  variants={slideVariants}
                  initial="enter"
                  animate="center"
                  exit="exit"
                  transition={{ type: 'spring', stiffness: 320, damping: 30, mass: 0.8 }}
                  drag="x"
                  dragConstraints={{ left: 0, right: 0 }}
                  dragElastic={0.15}
                  onDragEnd={(_, info) => {
                    if (info.offset.x < -60 || info.velocity.x < -250) navigate(1)
                    else if (info.offset.x > 60 || info.velocity.x > 250) navigate(-1)
                  }}
                  className="absolute inset-0 flex items-center justify-center p-4"
                >
                  <img
                    src={lightbox.hd_url ?? lightbox.output_url}
                    alt="result"
                    className="max-h-full max-w-full rounded-card object-contain"
                    draggable={false}
                  />
                </motion.div>
              </AnimatePresence>

              {/* Prev chevron */}
              {(lightboxIndex ?? 0) > 0 && (
                <button
                  onClick={() => navigate(-1)}
                  className="absolute left-1 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full bg-black/35 flex items-center justify-center"
                >
                  <ChevronLeft size={20} className="text-white/75" />
                </button>
              )}
              {/* Next chevron */}
              {lightboxIndex !== null && lightboxIndex < sorted.length - 1 && (
                <button
                  onClick={() => navigate(1)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full bg-black/35 flex items-center justify-center"
                >
                  <ChevronRight size={20} className="text-white/75" />
                </button>
              )}
            </div>

            {/* Reactions */}
            <div className="px-4 pb-2" onClick={(e) => e.stopPropagation()}>
              <ReactionRow
                jobId={lightbox.job_id}
                state={reactions[lightbox.job_id] ?? { counts: {}, mine: null }}
                compact={false}
                onReact={handleReact}
              />
            </div>

            {/* Action buttons */}
            <div
              className="grid grid-cols-2 gap-2 px-4 pt-3"
              style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)' }}
              onClick={(e) => e.stopPropagation()}
            >
              <a
                href={lightbox.hd_url ?? lightbox.output_url}
                download
                className="flex items-center justify-center gap-1.5 py-3 bg-white/10 rounded-card text-white text-[13px] font-medium"
              >
                <Download size={14} /> Save
              </a>
              <button className="flex items-center justify-center gap-1.5 py-3 bg-white/10 rounded-card text-white text-[13px] font-medium">
                <RefreshCw size={14} /> Redo
              </button>
              <button
                onClick={() => handleHD(lightbox)}
                disabled={!!lightbox.hd_url || hdLoading}
                className={`flex items-center justify-center gap-1.5 py-3 rounded-card text-[13px] font-medium ${
                  lightbox.hd_url ? 'bg-[#34C759]/30 text-[#34C759]' : 'bg-[#6C47FF]/30 text-[#A88FFF]'
                }`}
              >
                <Star size={14} /> {lightbox.hd_url ? 'HD ✓' : 'HD · 2⚡'}
              </button>
              <button
                onClick={() => handleCaption(lightbox)}
                className="flex items-center justify-center gap-1.5 py-3 bg-[#FF9500]/20 rounded-card text-[#FF9500] text-[13px] font-medium"
              >
                <Pencil size={14} /> Caption
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Leaderboard modal */}
      <AnimatePresence>
        {showLeaderboard && leaderboard && (
          <LeaderboardModal data={leaderboard} onClose={() => setShowLeaderboard(false)} />
        )}
      </AnimatePresence>

      {/* Caption sheet */}
      <AnimatePresence>
        {showCaptions && (
          <CaptionSheet
            captions={captions}
            loading={captionLoading}
            onClose={() => { setShowCaptions(false); setCaptions([]) }}
            onRegenerate={() => lightbox && regenerateCaption(lightbox)}
          />
        )}
      </AnimatePresence>
      </>, document.body)}
    </div>
  )
}
