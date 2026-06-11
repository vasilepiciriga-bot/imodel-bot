import { useState } from 'react'
import { motion } from 'framer-motion'
import { Download, Share2, RefreshCw, Sparkles, Star, Send } from 'lucide-react'
import { BeforeAfterSlider } from './BeforeAfterSlider'
import { useAppStore } from '../../store/appStore'
import { track } from '../../api/analytics'
import type { Generation } from '../../types'

const tg = window.Telegram?.WebApp

interface Props {
  job: Generation
  beforeUrl?: string
  onRegenerate: () => void
  onHD: () => void
  hdLoading?: boolean
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
    // Center image, maintain aspect ratio, fill 900×900 area
    const size = 900
    const x = (1080 - size) / 2
    const y = 200
    ctx.save()
    ctx.beginPath()
    ctx.roundRect(x, y, size, size, 32)
    ctx.clip()
    ctx.drawImage(img, x, y, size, size)
    ctx.restore()

    // Brand text
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

export function ResultCard({ job, beforeUrl, onRegenerate, onHD, hdLoading }: Props) {
  const [shareLoading, setShareLoading] = useState(false)
  const user = useAppStore((s) => s.user) as ({ bot_link?: string } | null)
  const botLink = (user as { bot_link?: string } | null)?.bot_link ?? 'https://t.me/imodelapp_bot'
  const outputUrl = job.hd_url ?? job.output_url ?? ''

  async function handleShare() {
    if (!outputUrl) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setShareLoading(true)
    try {
      // Method 1: Telegram native shareToStory (v7.8+, mobile only)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const tgAny = tg as any
      if (tgAny && typeof tgAny.shareToStory === 'function') {
        track('share_tapped', { method: 'story' })
        tgAny.shareToStory(outputUrl, {
          text: '✦ Made with iModel Studio',
          widget_link: { url: botLink, name: 'Try it free →' },
        })
        return
      }

      // Method 2: Build branded story card and download + show share link
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

      // Also open Telegram share dialog as fallback
      const shareText = encodeURIComponent('Look what AI made from my selfie! 🤩')
      const shareUrl = encodeURIComponent(botLink)
      tg?.openLink(`https://t.me/share/url?url=${shareUrl}&text=${shareText}`)
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
          Story
        </motion.button>
        <motion.a
          whileTap={{ scale: 0.96 }}
          href={outputUrl}
          download="imodel-result.jpg"
          className="flex items-center justify-center gap-2 py-3.5 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[13px] font-medium"
        >
          <Download size={15} /> Save
        </motion.a>
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
    </motion.div>
  )
}
