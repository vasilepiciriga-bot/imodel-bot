import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Download, RefreshCw, Star, Images, Trophy, Share2 } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { getGallery, getCachedGallery, setCachedGallery, requestHD } from '../api/generations'
import { getLeaderboard, type LeaderboardData } from '../api/leaderboard'
import { setPortfolioVisibility } from '../api/portfolio'
import { getMe } from '../api/session'
import { track } from '../api/analytics'
import type { Generation } from '../types'

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
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-8 h-1 bg-white/20 rounded-full" />
        </div>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div>
            <h2 className="text-[17px] font-bold text-white">🏆 Leaderboard</h2>
            <p className="text-[12px] text-white/50 mt-0.5">{period} · top generators</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
            <X size={16} className="text-white/70" />
          </button>
        </div>
        {/* Entries */}
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

export default function Gallery() {
  const gallery = useAppStore((s) => s.gallery)
  const setGallery = useAppStore((s) => s.setGallery)
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const [lightbox, setLightbox] = useState<Generation | null>(null)
  const [hdLoading, setHdLoading] = useState(false)
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null)
  const [showLeaderboard, setShowLeaderboard] = useState(false)
  const [portfolioLoading, setPortfolioLoading] = useState(false)

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

  async function handleHD(job: Generation) {
    setHdLoading(true)
    try {
      await requestHD(job.job_id)
      tg?.HapticFeedback?.notificationOccurred('success')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'HD failed'
      alert(msg)
    } finally {
      setHdLoading(false)
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

      {/* Leaderboard strip — shown when gallery has content */}
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
          <div className="columns-2 gap-2.5 pb-4">
            {gallery.map((item, i) => (
              <motion.div
                key={item.job_id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: Math.min(i * 0.04, 0.4) }}
                className="break-inside-avoid mb-2.5 relative"
                onClick={() => { tg?.HapticFeedback?.impactOccurred('light'); setLightbox(item) }}
              >
                <img
                  src={item.hd_url ?? item.output_url}
                  alt={item.preset_key ?? 'photo'}
                  loading="lazy"
                  className="w-full rounded-card object-cover"
                />
                {item.hd_url && (
                  <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] rounded-full text-[9px] text-white font-bold">
                    HD
                  </div>
                )}
                <div className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 bg-black/50 rounded-full text-[9px] text-white truncate max-w-[80%]">
                  {item.preset_key ?? item.mode ?? 'portrait'}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Lightbox */}
      <AnimatePresence>
        {lightbox && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/90 flex flex-col"
            onClick={() => setLightbox(null)}
          >
            <div className="flex items-center justify-between p-4">
              <span className="text-white text-[13px] font-medium">{lightbox.preset_key ?? lightbox.mode}</span>
              <button onClick={() => setLightbox(null)}>
                <X size={24} className="text-white" />
              </button>
            </div>

            <motion.div
              className="flex-1 flex items-center justify-center p-4"
              onClick={(e) => e.stopPropagation()}
            >
              <img
                src={lightbox.hd_url ?? lightbox.output_url}
                alt="result"
                className="max-h-full max-w-full rounded-card object-contain"
              />
            </motion.div>

            <div className="grid grid-cols-3 gap-2 p-4" onClick={(e) => e.stopPropagation()}>
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
    </div>
  )
}
