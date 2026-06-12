import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Download, Share2, RefreshCw, Sparkles, Star, Send, Users, Play } from 'lucide-react'
import { saveImageToPhone } from '../../lib/saveImage'
import { BeforeAfterSlider } from './BeforeAfterSlider'
import { useAppStore } from '../../store/appStore'
import { api } from '../../api/client'
import { shareToCommunity } from '../../api/community'
import { track } from '../../api/analytics'
import { useToast } from '../../hooks/useToast'
import { animateGeneration, createAgeTransform, getGeneration } from '../../api/generations'
import type { AgeDirection, Generation } from '../../types'

const tg = window.Telegram?.WebApp

const UPSELL_MODES = [
  { key: 'vogue',   emoji: '👑', label: 'Vogue',   desc: '8 shots · 4× upscale',   credits: 6 },
  { key: 'ceo',     emoji: '🤵', label: 'CEO',     desc: '6 shots · upscaled',      credits: 4 },
  { key: 'luxury',  emoji: '✨', label: 'Luxury',  desc: '6 shots · old money',     credits: 4 },
  { key: 'premium', emoji: '💎', label: 'Premium', desc: '4 shots · HD quality',    credits: 3 },
] as const

function pickUpsellMode(jobId: string) {
  const hash = jobId.charCodeAt(jobId.length - 1) + jobId.charCodeAt(0)
  return UPSELL_MODES[hash % UPSELL_MODES.length]
}

interface Props {
  job: Generation
  beforeUrl?: string
  onRegenerate: () => void
  onHD: () => void
  hdLoading?: boolean
  photoshootMode?: string
  onTryMode?: (modeKey: string) => void
}

async function buildStoryBlob(imageUrl: string): Promise<Blob | null> {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 1080
    canvas.height = 1920
    const ctx = canvas.getContext('2d')!
    const grad = ctx.createLinearGradient(0, 0, 1080, 1920)
    grad.addColorStop(0, '#0F0F1A')
    grad.addColorStop(1, '#1A0A2E')
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, 1080, 1920)

    const img = new Image()
    img.crossOrigin = 'anonymous'
    await new Promise<void>((res, rej) => {
      img.onload = () => res()
      img.onerror = rej
      img.src = imageUrl
    })
    const size = 900
    const x = (1080 - size) / 2
    const y = 200
    ctx.save()
    ctx.beginPath()
    ctx.roundRect(x, y, size, size, 32)
    ctx.clip()
    ctx.drawImage(img, x, y, size, size)
    ctx.restore()

    ctx.fillStyle = 'rgba(255,255,255,0.95)'
    ctx.font = 'bold 64px -apple-system, Helvetica Neue, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('✦ iModel Studio', 540, 1230)
    ctx.font = '40px -apple-system, Helvetica Neue, sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.6)'
    ctx.fillText('AI Photoshoots', 540, 1300)

    return await new Promise<Blob | null>((res) => canvas.toBlob(res, 'image/jpeg', 0.92))
  } catch {
    return null
  }
}

export function ResultCard({ job, beforeUrl, onRegenerate, onHD, hdLoading, photoshootMode, onTryMode }: Props) {
  const [shareLoading, setShareLoading] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)
  const [communityLabel, setCommunityLabel] = useState('')
  const [communitySharing, setCommunitySharing] = useState(false)
  const [communityShared, setCommunityShared] = useState(false)
  const [showCommunityInput, setShowCommunityInput] = useState(false)

  // Animate (Talking Photo)
  const [animating, setAnimating] = useState(false)
  const [animateJobId, setAnimateJobId] = useState<string | null>(job.animate_job_id ?? null)
  const [animateStatus, setAnimateStatus] = useState<string>('')
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const animatePollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Age transform
  const [ageDirection, setAgeDirection] = useState<AgeDirection | null>(null)
  const [ageJobId, setAgeJobId] = useState<string | null>(null)
  const [ageStatus, setAgeStatus] = useState<string>('')
  const [ageUrl, setAgeUrl] = useState<string | null>(null)
  const agePollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const user = useAppStore((s) => s.user) as ({ bot_link?: string } | null)
  const updateCredits = useAppStore((s) => s.updateCredits)
  const botLink = (user as { bot_link?: string } | null)?.bot_link ?? 'https://t.me/imodelapp_bot'
  const outputUrl = job.hd_url ?? job.output_url ?? ''
  const toast = useToast()

  // Poll animate job until ready/failed
  useEffect(() => {
    if (!animateJobId || videoUrl || animateStatus === 'failed') return
    animatePollRef.current = setInterval(async () => {
      try {
        const j = await getGeneration(animateJobId)
        setAnimateStatus(j.status)
        if (j.status === 'ready' && j.output_url) {
          setVideoUrl(j.output_url)
          clearInterval(animatePollRef.current!)
        } else if (j.status === 'failed' || j.status === 'error') {
          clearInterval(animatePollRef.current!)
        }
      } catch { /* network blip — keep polling */ }
    }, 3000)
    return () => clearInterval(animatePollRef.current!)
  }, [animateJobId])

  // Poll age transform job until ready/failed
  useEffect(() => {
    if (!ageJobId || ageUrl || ageStatus === 'failed') return
    agePollRef.current = setInterval(async () => {
      try {
        const j = await getGeneration(ageJobId)
        setAgeStatus(j.status)
        if (j.status === 'ready' && j.output_url) {
          setAgeUrl(j.output_url)
          clearInterval(agePollRef.current!)
        } else if (j.status === 'failed' || j.status === 'error') {
          clearInterval(agePollRef.current!)
        }
      } catch { /* network blip */ }
    }, 3000)
    return () => clearInterval(agePollRef.current!)
  }, [ageJobId])

  async function handleAnimate() {
    if (animating || animateJobId) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setAnimating(true)
    try {
      const res = await animateGeneration(job.job_id)
      setAnimateJobId(res.job_id)
      setAnimateStatus('queued')
      track('animate_started', { job_id: job.job_id })
      updateCredits(-res.credit_cost)
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 402) toast.error('Not enough credits (10⚡ needed)')
      else toast.error('Could not start animation — try again')
    } finally {
      setAnimating(false)
    }
  }

  async function handleAgeTransform(direction: AgeDirection) {
    if (ageJobId) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setAgeDirection(direction)
    try {
      const res = await createAgeTransform(job.job_id, direction)
      setAgeJobId(res.job_id)
      setAgeStatus('queued')
      track('age_transform_started', { job_id: job.job_id, direction })
      updateCredits(-res.credit_cost)
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status
      if (status === 402) toast.error('Not enough credits (4⚡ needed)')
      else toast.error('Could not start age transform — try again')
      setAgeDirection(null)
    }
  }

  const upsellMode = pickUpsellMode(job.job_id)
  const showUpsell = (photoshootMode === 'everyday' || !photoshootMode) && !!onTryMode

  async function claimShareReward() {
    try {
      const result = await api.post<{ ok: boolean; credits: number; earned: number }>('/api/v1/share-reward')
      if (result.ok) {
        updateCredits(result.credits)
        toast.success(`+${result.earned}⚡ earned for sharing!`, { icon: '🎁' })
      }
    } catch {
      // Already claimed today — silent
    }
  }

  async function handleSubmitCommunity() {
    if (!communityLabel.trim()) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setCommunitySharing(true)
    try {
      const result = await shareToCommunity(job.job_id, communityLabel.trim())
      if (result.already_shared) {
        toast.success('Already in the gallery!', { icon: '✅' })
      } else {
        track('community_submitted', { job_id: job.job_id })
        toast.success('Added to Community Gallery!', { icon: '🎉', sub: 'Others can vote on your photo' })
      }
      setCommunityShared(true)
      setShowCommunityInput(false)
    } catch {
      toast.error('Could not submit — try again')
    } finally {
      setCommunitySharing(false)
    }
  }

  async function handleShare() {
    if (!outputUrl) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setShareLoading(true)
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgAny = tg as any
      if (tgAny && typeof tgAny.shareToStory === 'function') {
        track('share_tapped', { method: 'story' })
        tgAny.shareToStory(outputUrl, {
          text: '✦ Made with iModel Studio',
          widget_link: { url: botLink, name: 'Try it free →' },
        })
        await claimShareReward()
        return
      }

      track('share_tapped', { method: 'story_canvas' })
      const blob = await buildStoryBlob(outputUrl)
      if (blob) {
        const blobUrl = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = blobUrl
        a.download = 'imodel-story.jpg'
        a.click()
        URL.revokeObjectURL(blobUrl)
      }

      const shareText = encodeURIComponent('Look what AI made from my selfie! 🤩')
      const shareUrl = encodeURIComponent(botLink)
      tg?.openLink(`https://t.me/share/url?url=${shareUrl}&text=${shareText}`)
      await claimShareReward()
    } finally {
      setShareLoading(false)
    }
  }

  async function handleForward() {
    tg?.HapticFeedback?.impactOccurred('light')
    track('share_tapped', { method: 'forward' })
    const shareText = encodeURIComponent('Look what AI made from my selfie 🤩 →')
    const url = encodeURIComponent(botLink)
    tg?.openLink(`https://t.me/share/url?url=${url}&text=${shareText}`)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="space-y-3"
    >
      {beforeUrl && outputUrl ? (
        <BeforeAfterSlider before={beforeUrl} after={outputUrl} />
      ) : (
        <div className="rounded-card overflow-hidden">
          <img src={outputUrl} alt="result" className="w-full object-cover" />
        </div>
      )}

      {/* Tournament badge — shown for photoshoot modes that ran a multi-candidate tournament */}
      {(job.candidates_total ?? 0) > 1 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.35, type: 'spring', stiffness: 400, damping: 28 }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#6C47FF]/8 border border-[#6C47FF]/15 self-start w-fit"
        >
          <span className="text-[11px]">🏆</span>
          <span className="text-[11px] font-semibold text-[#6C47FF]">
            Best of {job.candidates_total} candidates
          </span>
          {(job.best_score ?? 0) > 0 && (
            <span className="text-[10px] text-[#6C47FF]/55">· {job.best_score}pts</span>
          )}
        </motion.div>
      )}

      {/* Primary actions: Share + Save */}
      <div className="grid grid-cols-2 gap-2">
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={handleShare}
          disabled={shareLoading}
          className="flex items-center justify-center gap-2 py-3.5 rounded-card bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[13px] font-semibold"
        >
          {shareLoading
            ? <Sparkles size={15} className="animate-spin" />
            : <Share2 size={15} />}
          Story · +2⚡
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          disabled={saveLoading}
          onClick={async () => {
            setSaveLoading(true)
            tg?.HapticFeedback?.impactOccurred('medium')
            try {
              await saveImageToPhone(outputUrl)
            } catch {
              window.open(outputUrl, '_blank')
            } finally { setSaveLoading(false) }
          }}
          className="flex items-center justify-center gap-2 py-3.5 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[13px] font-medium disabled:opacity-50"
        >
          <Download size={15} /> {saveLoading ? 'Saving…' : 'Save'}
        </motion.button>
      </div>

      {/* Secondary actions: Forward + Regen + HD */}
      <div className="grid grid-cols-3 gap-2">
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={handleForward}
          className="flex items-center justify-center gap-1.5 py-2.5 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[12px] font-medium"
        >
          <Send size={13} /> Forward
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={onRegenerate}
          className="flex items-center justify-center gap-1.5 py-2.5 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[12px] font-medium"
        >
          <RefreshCw size={13} /> Again
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => { tg?.HapticFeedback?.impactOccurred('medium'); onHD() }}
          disabled={!!job.hd_url || hdLoading}
          className={`flex items-center justify-center gap-1.5 py-2.5 rounded-card text-[12px] font-medium ${
            job.hd_url ? 'bg-[#34C759]/20 text-[#34C759]' : 'bg-[#6C47FF]/10 text-[#6C47FF]'
          }`}
        >
          {hdLoading ? <Sparkles size={13} className="animate-spin" /> : <Star size={13} />}
          {job.hd_url ? 'HD ✓' : 'HD · 2⚡'}
        </motion.button>
      </div>

      {/* ── Animate (Talking Photo / AI Alive) ── */}
      {!videoUrl && (
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={handleAnimate}
          disabled={animating || !!animateJobId}
          className={`w-full flex items-center justify-center gap-2 py-3 rounded-card text-[13px] font-semibold transition-colors ${
            animateJobId && !videoUrl
              ? 'bg-[#1C1C2E] text-[#A78BFF]'
              : 'bg-gradient-to-r from-[#2C1654] to-[#1A0A2E] text-white'
          }`}
        >
          {animating || (animateJobId && !videoUrl && animateStatus !== 'failed') ? (
            <Sparkles size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
          {animating
            ? 'Starting…'
            : animateJobId && animateStatus !== 'failed' && !videoUrl
              ? 'Animating… (1-3 min)'
              : animateStatus === 'failed'
                ? '⚠ Animation failed — retry?'
                : '✨ Animate · 10⚡'}
        </motion.button>
      )}

      {/* Video player — shown when animate job is ready */}
      {videoUrl && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-card overflow-hidden"
        >
          <video
            src={videoUrl}
            controls
            autoPlay
            loop
            playsInline
            className="w-full object-cover"
          />
          <div className="flex items-center justify-between px-3 py-2 bg-[#1C1C2E]">
            <span className="text-[11px] text-[#A78BFF] font-medium">✨ AI Alive</span>
            <motion.button
              whileTap={{ scale: 0.94 }}
              onClick={async () => {
                tg?.HapticFeedback?.impactOccurred('light')
                try { await saveImageToPhone(videoUrl) } catch { window.open(videoUrl, '_blank') }
              }}
              className="text-[11px] text-white/60 flex items-center gap-1"
            >
              <Download size={11} /> Save video
            </motion.button>
          </div>
        </motion.div>
      )}

      {/* ── Age Transformation ── */}
      {!ageUrl && (
        <div className="space-y-2">
          <p className="text-[11px] text-[#6E6E73] font-medium px-0.5">Age Transform · 4⚡ each</p>
          <div className="grid grid-cols-4 gap-1.5">
            {([
              { dir: 'baby',  label: '👶 Baby',  disabled: !!ageJobId },
              { dir: 'young', label: '🧑 Young',  disabled: !!ageJobId },
              { dir: 'older', label: '🧓 +20y',   disabled: !!ageJobId },
              { dir: 'elder', label: '👴 +40y',   disabled: !!ageJobId },
            ] as const).map(({ dir, label, disabled }) => (
              <motion.button
                key={dir}
                whileTap={{ scale: 0.93 }}
                disabled={disabled}
                onClick={() => handleAgeTransform(dir)}
                className={`py-2 rounded-[12px] text-[11px] font-medium transition-colors ${
                  ageDirection === dir && ageJobId
                    ? 'bg-[#6C47FF]/20 text-[#6C47FF] border border-[#6C47FF]/40'
                    : 'bg-[#F5F5F7] text-[#1D1D1F] disabled:opacity-40'
                }`}
              >
                {ageDirection === dir && ageJobId && ageStatus !== 'failed' && !ageUrl
                  ? '…'
                  : label}
              </motion.button>
            ))}
          </div>
          {ageDirection && ageJobId && ageStatus !== 'failed' && !ageUrl && (
            <p className="text-[11px] text-[#6C47FF] text-center animate-pulse">
              Transforming age… (30–60 sec)
            </p>
          )}
          {ageStatus === 'failed' && (
            <p className="text-[11px] text-[#FF3B30] text-center">Age transform failed — try again</p>
          )}
        </div>
      )}

      {/* Age transform result */}
      {ageUrl && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-1.5"
        >
          <p className="text-[11px] text-[#6E6E73] font-medium">Age Transform result</p>
          <div className="rounded-card overflow-hidden">
            <img src={ageUrl} alt="age transformed" className="w-full object-cover" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={async () => {
                try { await saveImageToPhone(ageUrl) } catch { window.open(ageUrl, '_blank') }
              }}
              className="flex items-center justify-center gap-1.5 py-2.5 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[12px] font-medium"
            >
              <Download size={13} /> Save
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={() => { setAgeUrl(null); setAgeJobId(null); setAgeDirection(null); setAgeStatus('') }}
              className="flex items-center justify-center gap-1.5 py-2.5 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[12px] font-medium"
            >
              <RefreshCw size={13} /> Try another
            </motion.button>
          </div>
        </motion.div>
      )}

      {/* Premium mode upsell — only after everyday mode */}
      {showUpsell && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="flex items-center gap-3 px-3.5 py-3 rounded-[16px] border"
          style={{
            background: 'linear-gradient(135deg, rgba(108,71,255,0.06), rgba(255,45,120,0.06))',
            borderColor: 'rgba(108,71,255,0.20)',
          }}
        >
          <span className="text-[22px] flex-shrink-0">{upsellMode.emoji}</span>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-bold text-[#1D1D1F] leading-tight">
              See this in {upsellMode.label} mode
            </p>
            <p className="text-[11px] text-[#6E6E73] truncate">
              {upsellMode.desc} · {upsellMode.credits}⚡
            </p>
          </div>
          <motion.button
            whileTap={{ scale: 0.94 }}
            onClick={() => {
              tg?.HapticFeedback?.impactOccurred('medium')
              track('upsell_mode_tapped', { from: 'result_card', mode: upsellMode.key })
              onTryMode!(upsellMode.key)
            }}
            className="px-3 py-1.5 rounded-[10px] text-white text-[12px] font-bold flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
          >
            Try →
          </motion.button>
        </motion.div>
      )}

      {/* Submit to Community Gallery */}
      {!communityShared && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <AnimatePresence mode="wait">
            {showCommunityInput ? (
              <motion.div
                key="input"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="flex gap-2 items-center">
                  <input
                    autoFocus
                    value={communityLabel}
                    onChange={(e) => setCommunityLabel(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitCommunity() }}
                    placeholder="Style name for the gallery…"
                    className="flex-1 px-3 py-2.5 rounded-[12px] bg-[#F5F5F7] text-[13px] text-[#1D1D1F] placeholder-[#B0B0B8] outline-none border border-[#6C47FF]/30 focus:border-[#6C47FF]"
                  />
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={handleSubmitCommunity}
                    disabled={!communityLabel.trim() || communitySharing}
                    className="px-3 py-2.5 rounded-[12px] bg-[#6C47FF] text-white text-[12px] font-bold disabled:opacity-50 flex-shrink-0"
                  >
                    {communitySharing ? '…' : 'Post'}
                  </motion.button>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setShowCommunityInput(false)}
                    className="px-2.5 py-2.5 rounded-[12px] bg-[#F5F5F7] text-[#6E6E73] text-[12px]"
                  >
                    ✕
                  </motion.button>
                </div>
              </motion.div>
            ) : (
              <motion.button
                key="cta"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => { tg?.HapticFeedback?.selectionChanged(); setShowCommunityInput(true) }}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-[12px] bg-[#F5F5F7] text-[#6E6E73] text-[12px] font-medium"
              >
                <Users size={13} />
                Submit to Community Gallery
              </motion.button>
            )}
          </AnimatePresence>
        </motion.div>
      )}

      {communityShared && (
        <p className="text-center text-[11px] text-[#34C759] font-semibold py-1">
          ✓ In the Community Gallery — others can vote!
        </p>
      )}
    </motion.div>
  )
}
