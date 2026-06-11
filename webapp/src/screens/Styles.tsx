import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, TrendingUp, Check, X } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { fetchPresets, getCachedPresets, setCachedPresets } from '../api/presets'
import { createInvoice } from '../api/shop'
import { useToast } from '../hooks/useToast'
import { hap } from '../lib/haptics'
import { PresetSkeleton } from '../components/shared/SkeletonLoader'
import type { Preset } from '../types'

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

const CATEGORIES = ['All', 'Studio', 'Cinematic', 'Outdoor', 'Lifestyle', 'Artistic', '★ Premium']

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
      </div>
    </motion.button>
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
              <span className="text-[12px] font-semibold" style={{ color: accent }}>{preset.category}</span>
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
  const activePreset = useAppStore((s) => s.activePreset)
  const setActivePreset = useAppStore((s) => s.setActivePreset)
  const setTab = useAppStore((s) => s.setTab)
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const toast = useToast()

  useEffect(() => {
    const cached = getCachedPresets()
    if (cached) { setPresets(cached); setLoading(false); return }
    fetchPresets()
      .then(({ presets }) => { setPresets(presets); setCachedPresets(presets) })
      .catch(() => toast.error('Failed to load styles'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = category === 'All'
    ? presets
    : category === '★ Premium'
    ? presets.filter((p) => p.is_premium)
    : presets.filter((p) => p.category.toLowerCase() === category.toLowerCase())

  const trending = presets.filter((p) => !p.is_premium && !p.locked).slice(0, 6)

  async function handlePreset(preset: Preset) {
    if (preset.locked && preset.pack_id) {
      hap.medium()
      try {
        const { invoice_url } = await createInvoice(preset.pack_id)
        tg?.openInvoice(invoice_url, (status: string) => {
          if (status === 'paid' && user) {
            setUser({ ...user, unlocked_packs: [...(user.unlocked_packs ?? []), preset.pack_id!] })
            toast.success('Style pack unlocked!', { icon: '🎉', sub: preset.label + ' and more are now available' })
          }
        })
      } catch { toast.error('Could not open payment') }
      setPreview(null)
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
      <div className="px-4 pt-4 pb-1">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">🎭 Styles</h1>
        <p className="text-[13px] text-[#6E6E73]">Tap to apply · hold to preview</p>
      </div>

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
            {filtered.map((preset, i) => (
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
      </AnimatePresence>
    </div>
  )
}
