import { useState } from 'react'
import { motion } from 'framer-motion'
import { Download, Share2, RefreshCw, Sparkles, Star, Send } from 'lucide-react'
import { saveImageToPhone } from '../../lib/saveImage'
import { BeforeAfterSlider } from './BeforeAfterSlider'
import { useAppStore } from '../../store/appStore'
import { api } from '../../api/client'
import { track } from '../../api/analytics'
import { useToast } from '../../hooks/useToast'
import type { Generation } from '../../types'

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
  const user = useAppStore((s) => s.user) as ({ bot_link?: string } | null)
  const updateCredits = useAppStore((s) => s.updateCredits)
  const botLink = (user as { bot_link?: string } | null)?.bot_link ?? 'https://t.me/imodelapp_bot'
  const outputUrl = job.hd_url ?? job.output_url ?? ''
  const toast = useToast()

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
    </motion.div>
  )
}
