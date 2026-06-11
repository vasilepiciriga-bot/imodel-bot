import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Download, RefreshCw, Star, Images } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { getGallery, getCachedGallery, setCachedGallery, requestHD } from '../api/generations'
import type { Generation } from '../types'

const tg = window.Telegram?.WebApp

export default function Gallery() {
  const gallery = useAppStore((s) => s.gallery)
  const setGallery = useAppStore((s) => s.setGallery)
  const [lightbox, setLightbox] = useState<Generation | null>(null)
  const [hdLoading, setHdLoading] = useState(false)

  useEffect(() => {
    const cached = getCachedGallery()
    if (cached?.length) { setGallery(cached); return }
    getGallery().then(({ items }) => {
      setGallery(items)
      setCachedGallery(items)
    }).catch(() => null)
  }, [setGallery])

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

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🖼 Gallery</h1>
        {gallery.length > 0 && (
          <span className="text-[13px] text-[#6E6E73]">{gallery.length} photos</span>
        )}
      </div>

      {gallery.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-8 text-center">
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#6C47FF]/20 to-[#FF2D78]/20 flex items-center justify-center">
            <Images size={32} className="text-[#6C47FF]" />
          </div>
          <div>
            <p className="text-[17px] font-semibold text-[#1D1D1F]">No photos yet</p>
            <p className="text-[14px] text-[#6E6E73] mt-1">Generate your first AI photo in Studio</p>
          </div>
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
              layoutId={`gallery-${lightbox.job_id}`}
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
    </div>
  )
}
