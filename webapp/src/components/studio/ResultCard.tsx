import { motion } from 'framer-motion'
import { Download, Share2, RefreshCw, Sparkles, Star } from 'lucide-react'
import { BeforeAfterSlider } from './BeforeAfterSlider'
import type { Generation } from '../../types'

const tg = window.Telegram?.WebApp

interface Props {
  job: Generation
  beforeUrl?: string
  onRegenerate: () => void
  onHD: () => void
  hdLoading?: boolean
}

async function shareToStories(imageUrl: string) {
  const canvas = document.createElement('canvas')
  canvas.width = 1080
  canvas.height = 1920
  const ctx = canvas.getContext('2d')!

  const grad = ctx.createLinearGradient(0, 0, 1080, 1920)
  grad.addColorStop(0, '#6C47FF')
  grad.addColorStop(1, '#FF2D78')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 1080, 1920)

  const img = new Image()
  img.crossOrigin = 'anonymous'
  await new Promise<void>((res) => { img.onload = () => res(); img.src = imageUrl })
  ctx.drawImage(img, 90, 180, 900, 900)

  ctx.fillStyle = 'white'
  ctx.font = 'bold 56px -apple-system, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('iModel Studio', 540, 1200)
  ctx.font = '36px -apple-system, sans-serif'
  ctx.fillStyle = 'rgba(255,255,255,0.8)'
  ctx.fillText('Create yours with AI', 540, 1270)

  canvas.toBlob((blob) => {
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'imodel-result.jpg'
    a.click()
    URL.revokeObjectURL(url)
  }, 'image/jpeg', 0.9)
}

export function ResultCard({ job, beforeUrl, onRegenerate, onHD, hdLoading }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="space-y-3"
    >
      {beforeUrl && job.output_url ? (
        <BeforeAfterSlider before={beforeUrl} after={job.hd_url ?? job.output_url} />
      ) : (
        <div className="rounded-card overflow-hidden">
          <img src={job.hd_url ?? job.output_url} alt="result" className="w-full object-cover" />
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <motion.a
          whileTap={{ scale: 0.96 }}
          href={job.hd_url ?? job.output_url}
          download="imodel-result.jpg"
          className="flex items-center justify-center gap-2 py-3 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[13px] font-medium"
        >
          <Download size={15} /> Save
        </motion.a>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => shareToStories(job.hd_url ?? job.output_url!)}
          className="flex items-center justify-center gap-2 py-3 rounded-card bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[13px] font-medium"
        >
          <Share2 size={15} /> Stories
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={onRegenerate}
          className="flex items-center justify-center gap-2 py-3 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[13px] font-medium"
        >
          <RefreshCw size={15} /> Try again
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => { tg?.HapticFeedback?.impactOccurred('medium'); onHD() }}
          disabled={!!job.hd_url || hdLoading}
          className={`flex items-center justify-center gap-2 py-3 rounded-card text-[13px] font-medium ${
            job.hd_url ? 'bg-[#34C759]/20 text-[#34C759]' : 'bg-[#6C47FF]/10 text-[#6C47FF]'
          }`}
        >
          {hdLoading ? <Sparkles size={15} className="animate-spin" /> : <Star size={15} />}
          {job.hd_url ? 'HD Done' : 'HD · 2⚡'}
        </motion.button>
      </div>
    </motion.div>
  )
}
