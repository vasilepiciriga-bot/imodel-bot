import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Check, Crown } from 'lucide-react'
import type { PhotoshootMode, PhotoshootModeKey } from '../../types'
import { track } from '../../api/analytics'
import { getVariantSync } from '../../api/experiments'

const tg = window.Telegram?.WebApp

const BADGE_LABELS: Record<string, string> = {
  popular: '🔥 Popular',
  best_quality: '👑 Best',
  for_business: '💼 Business',
  viral: '🔥 Viral',
  new: '✨ New',
  trending: '📈 Trending',
}

const CATEGORY_TABS = [
  { key: 'all', label: 'All', emoji: '⭐' },
  { key: 'viral', label: 'Viral', emoji: '🔥' },
  { key: 'events', label: 'Events', emoji: '🎉' },
  { key: 'pop_culture', label: 'Pop', emoji: '🎭' },
  { key: 'fashion', label: 'Fashion', emoji: '👑' },
  { key: 'lifestyle', label: 'Lifestyle', emoji: '✨' },
  { key: 'career', label: 'Career', emoji: '💼' },
  { key: 'social', label: 'Social', emoji: '💫' },
  { key: 'fantasy', label: 'Fantasy', emoji: '🧙' },
  { key: 'basics', label: 'Basics', emoji: '📸' },
  { key: 'creative', label: 'Custom', emoji: '🎨' },
]

function formatExpiresAt(ts: number): string {
  const d = new Date(ts * 1000)
  const now = Date.now()
  const diffDays = Math.ceil((d.getTime() - now) / 86400000)
  if (diffDays <= 0) return ''
  if (diffDays <= 3) return `⏰ ${diffDays}d left`
  return `⏰ Ends ${d.toLocaleDateString('en', { month: 'short', day: 'numeric' })}`
}

const MODE_COLOR_MAP: Record<string, { from: string; to: string }> = {
  everyday:         { from: '#6C47FF', to: '#8B67FF' },
  premium:          { from: '#6C47FF', to: '#FF2D78' },
  vogue:            { from: '#1A1A2E', to: '#8B0000' },
  ceo:              { from: '#1A3A5C', to: '#2E6CB5' },
  dating:           { from: '#FF6B6B', to: '#FFD93D' },
  luxury:           { from: '#B8860B', to: '#FFD700' },
  custom:           { from: '#0F2027', to: '#203A43' },
  action_figure:    { from: '#FF6B35', to: '#F7C59F' },
  met_gala:         { from: '#2C003E', to: '#C0392B' },
  halloween:        { from: '#2C1654', to: '#FF6600' },
  christmas_card:   { from: '#1A5C2E', to: '#C0392B' },
  valentines:       { from: '#C0392B', to: '#FF69B4' },
  coachella:        { from: '#8B4513', to: '#F4D03F' },
  wedding:          { from: '#7D6E83', to: '#C9A96E' },
  doctor:           { from: '#1A6B8A', to: '#48CAE4' },
  lawyer:           { from: '#2C3E50', to: '#566573' },
  real_estate:      { from: '#1A5276', to: '#27AE60' },
  podcast_host:     { from: '#6C3483', to: '#A569BD' },
  fitness_model:    { from: '#E74C3C', to: '#F39C12' },
  disney_princess:  { from: '#1A6B8A', to: '#DDA0DD' },
  anime_hero:       { from: '#1A1A2E', to: '#E91E8C' },
  superhero:        { from: '#1B2A4A', to: '#C0392B' },
  movie_poster:     { from: '#0D0D0D', to: '#C0392B' },
  rockstar:         { from: '#1A1A1A', to: '#8B0000' },
  cyberpunk:        { from: '#0D001A', to: '#00FFFF' },
  medieval_knight:  { from: '#2C3E50', to: '#85929E' },
  fairy_tale:       { from: '#1A0033', to: '#9B59B6' },
  space_explorer:   { from: '#0D001A', to: '#3498DB' },
  pirate:           { from: '#2C1654', to: '#8B4513' },
  dubai_influencer: { from: '#1A1A00', to: '#FFD700' },
  bali_creator:     { from: '#1B4332', to: '#52B788' },
  cottagecore:      { from: '#3D5A3E', to: '#FFDDD2' },
  y2k:              { from: '#6B0AC9', to: '#FF69B4' },
  old_money_portrait: { from: '#2C3E50', to: '#C9A96E' },
}
const DEFAULT_COLOR = { from: '#6C47FF', to: '#8B67FF' }

function getModeColor(key: string) {
  return MODE_COLOR_MAP[key] ?? DEFAULT_COLOR
}

interface Props {
  open: boolean
  onClose: () => void
  onSelect: (mode: PhotoshootModeKey, customDesc?: string, styleVariant?: string) => void
  onUpgrade?: () => void
  currentMode: PhotoshootModeKey
  userCredits: number
  modes: PhotoshootMode[]
}

export function PhotoshootModePicker({ open, onClose, onSelect, onUpgrade, currentMode, userCredits, modes }: Props) {
  const [selected, setSelected] = useState<PhotoshootModeKey>(currentMode)
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [customDesc, setCustomDesc] = useState('')
  const [selectedVariant, setSelectedVariant] = useState<string>('')
  const [upgradeMode, setUpgradeMode] = useState<PhotoshootMode | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const tabsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setSelected(currentMode)
    setUpgradeMode(null)
    setSelectedVariant('')
  }, [currentMode, open])

  // Reset category when opened
  useEffect(() => {
    if (open) setActiveCategory('all')
  }, [open])

  // Android back button support
  useEffect(() => {
    if (!open) return
    window.history.pushState({ modePicker: true }, '')
    const onPop = () => { setUpgradeMode(null); onClose() }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [open, onClose])

  const selectedMode = modes.find((m) => m.key === selected)

  const filteredModes = activeCategory === 'all'
    ? modes
    : modes.filter((m) => m.category === activeCategory)

  // Only show category tabs that have at least 1 mode
  const availableCategories = CATEGORY_TABS.filter(
    (tab) => tab.key === 'all' || modes.some((m) => m.category === tab.key)
  )

  function handleModeSelect(mode: PhotoshootMode) {
    tg?.HapticFeedback?.selectionChanged()
    setSelected(mode.key)
    setSelectedVariant('')
    if (mode.key !== 'custom') setCustomDesc('')
    const effectiveCost = mode.credits_for_user ?? mode.credits
    if (mode.is_premium && userCredits < effectiveCost + 4) {
      const variant = getVariantSync('upgrade_sheet')
      track('premium_mode_upgrade_shown', { mode: mode.key, credits: userCredits, variant })
      if (variant === 'paywall') {
        onClose()
        onUpgrade?.()
      } else {
        setUpgradeMode(mode)
      }
    } else {
      setUpgradeMode(null)
    }
  }

  function handleConfirm() {
    tg?.HapticFeedback?.impactOccurred('medium')
    if (selected === 'custom' && !customDesc.trim()) {
      textareaRef.current?.focus()
      return
    }
    track('mode_selected', { mode: selected, credits: selectedMode?.credits, variant: selectedVariant || undefined })
    onSelect(selected, selected === 'custom' ? customDesc.trim() : undefined, selectedVariant || undefined)
  }

  function handleUpgradeSubscribe() {
    const variant = getVariantSync('upgrade_sheet')
    track('premium_mode_subscribe_tapped', { mode: upgradeMode?.key, variant })
    setUpgradeMode(null)
    onClose()
    onUpgrade?.()
  }

  function handleUpgradeUseCredits() {
    if (!upgradeMode) return
    tg?.HapticFeedback?.impactOccurred('medium')
    const variant = getVariantSync('upgrade_sheet')
    track('premium_mode_use_credits', { mode: upgradeMode.key, credits: userCredits, variant })
    setUpgradeMode(null)
    onSelect(upgradeMode.key)
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/50"
            onClick={onClose}
          />

          {/* Bottom sheet */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-[24px] shadow-2xl"
            style={{ maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-8 h-1 bg-gray-200 rounded-full" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-black/[0.06]">
              <div>
                <h2 className="text-[17px] font-bold text-[#1D1D1F]">Choose Style</h2>
                <p className="text-[11px] text-[#6E6E73]">{modes.length} styles available</p>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-full bg-[#F5F5F7] flex items-center justify-center"
              >
                <X size={16} className="text-[#6E6E73]" />
              </button>
            </div>

            {/* Category tabs */}
            <div
              ref={tabsRef}
              className="flex gap-2 px-4 py-2.5 overflow-x-auto border-b border-black/[0.06]"
              style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}
            >
              {availableCategories.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => {
                    tg?.HapticFeedback?.selectionChanged()
                    setActiveCategory(tab.key)
                  }}
                  className={`flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all ${
                    activeCategory === tab.key
                      ? 'bg-[#6C47FF] text-white'
                      : 'bg-[#F5F5F7] text-[#6E6E73]'
                  }`}
                >
                  <span>{tab.emoji}</span>
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Mode list */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
              {filteredModes.length === 0 && (
                <div className="text-center py-8 text-[13px] text-[#6E6E73]">No styles in this category</div>
              )}

              {filteredModes.map((mode) => {
                const isSelected = selected === mode.key
                const colors = getModeColor(mode.key)
                const effectiveCredits = mode.credits_for_user ?? mode.credits
                const canAfford = userCredits >= effectiveCredits
                return (
                  <motion.button
                    key={mode.key}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleModeSelect(mode)}
                    className={`w-full flex items-center gap-3 p-3.5 rounded-[16px] border-2 transition-colors text-left ${
                      isSelected ? 'border-[#6C47FF]' : 'border-transparent bg-[#F5F5F7]'
                    }`}
                    style={isSelected ? { background: `linear-gradient(135deg, ${colors.from}12, ${colors.to}18)` } : {}}
                  >
                    {/* Emoji circle */}
                    <div
                      className="w-12 h-12 rounded-[12px] flex items-center justify-center text-[24px] flex-shrink-0"
                      style={{ background: `linear-gradient(135deg, ${colors.from}, ${colors.to})` }}
                    >
                      {mode.emoji}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[15px] font-semibold text-[#1D1D1F]">{mode.label}</span>
                        {mode.is_premium && (
                          <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-gradient-to-r from-[#FF9500] to-[#FF2D78] text-white">
                            <Crown size={8} strokeWidth={3} />PRO
                          </span>
                        )}
                        {mode.badge && !mode.is_premium && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white">
                            {BADGE_LABELS[mode.badge] ?? mode.badge}
                          </span>
                        )}
                        {mode.expires_at && formatExpiresAt(mode.expires_at) && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-[#FF9500]/15 text-[#FF9500]">
                            {formatExpiresAt(mode.expires_at)}
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-[#6E6E73] mt-0.5 truncate">{mode.short_desc}</p>
                    </div>

                    {/* Cost + check */}
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <div className="flex items-center gap-1">
                        {mode.credits_for_user != null && mode.credits_for_user < mode.credits && (
                          <span className="text-[11px] text-[#AEAEB2] line-through">{mode.credits}⚡</span>
                        )}
                        <span className={`text-[13px] font-bold ${canAfford ? 'text-[#6C47FF]' : 'text-[#FF3B30]'}`}>
                          {effectiveCredits}⚡
                        </span>
                      </div>
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-[#6C47FF] flex items-center justify-center">
                          <Check size={11} className="text-white" strokeWidth={3} />
                        </div>
                      )}
                    </div>
                  </motion.button>
                )
              })}

              {/* Style variant chips — shown when selected mode has variants */}
              <AnimatePresence>
                {selectedMode && Object.keys(selectedMode.style_variants ?? {}).length > 0 && selected !== 'custom' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden pt-1"
                  >
                    <p className="text-[11px] font-semibold text-[#6E6E73] mb-2 px-1">Style variant</p>
                    <div className="flex flex-wrap gap-2">
                      <motion.button
                        key="__default"
                        whileTap={{ scale: 0.95 }}
                        onClick={() => { tg?.HapticFeedback?.selectionChanged(); setSelectedVariant('') }}
                        className={`px-3 py-1.5 rounded-full text-[12px] font-semibold border transition-colors ${
                          !selectedVariant ? 'bg-[#6C47FF] text-white border-[#6C47FF]' : 'bg-[#F5F5F7] text-[#6E6E73] border-transparent'
                        }`}
                      >
                        Default
                      </motion.button>
                      {Object.entries(selectedMode.style_variants).map(([vk, vc]) => (
                        <motion.button
                          key={vk}
                          whileTap={{ scale: 0.95 }}
                          onClick={() => { tg?.HapticFeedback?.selectionChanged(); setSelectedVariant(vk) }}
                          className={`px-3 py-1.5 rounded-full text-[12px] font-semibold border transition-colors ${
                            selectedVariant === vk ? 'bg-[#6C47FF] text-white border-[#6C47FF]' : 'bg-[#F5F5F7] text-[#6E6E73] border-transparent'
                          }`}
                        >
                          {vc.label}
                        </motion.button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Custom mode: inline textarea */}
              <AnimatePresence>
                {selected === 'custom' && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="pt-1 pb-2">
                      <textarea
                        ref={textareaRef}
                        value={customDesc}
                        onChange={(e) => setCustomDesc(e.target.value)}
                        placeholder="Describe your vision... (e.g. «business portrait in New York», «summer at the beach», «fashion editorial»)"
                        rows={3}
                        className="w-full px-4 py-3 rounded-[14px] bg-[#F5F5F7] text-[13px] text-[#1D1D1F] placeholder-[#6E6E73] resize-none outline-none border border-[#6C47FF]/30 focus:border-[#6C47FF]"
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Bottom padding */}
              <div className="h-2" />
            </div>

            {/* Bottom CTA — upgrade sheet or normal confirm */}
            <AnimatePresence mode="wait">
              {upgradeMode ? (
                <motion.div
                  key="upgrade"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                  className="px-4 pb-safe pt-3 border-t border-black/[0.06] space-y-2.5"
                >
                  {/* Mode preview info */}
                  <div className="flex items-center gap-3 px-3 py-2.5 rounded-[14px] bg-gradient-to-r from-[#6C47FF]/8 to-[#FF2D78]/8">
                    <span className="text-[26px]">{upgradeMode.emoji}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-bold text-[#1D1D1F]">
                        <Crown size={12} className="inline text-[#FF9500] mr-1" strokeWidth={2.5} />
                        {upgradeMode.label}
                      </p>
                      <p className="text-[11px] text-[#6E6E73] truncate">{upgradeMode.short_desc}</p>
                    </div>
                    <div className="flex items-center gap-1">
                      {upgradeMode.credits_for_user != null && upgradeMode.credits_for_user < upgradeMode.credits && (
                        <span className="text-[11px] text-[#AEAEB2] line-through">{upgradeMode.credits}⚡</span>
                      )}
                      <span className="text-[13px] font-bold text-[#FF9500]">
                        {upgradeMode.credits_for_user ?? upgradeMode.credits}⚡
                      </span>
                    </div>
                  </div>
                  {/* Two-button choice */}
                  <div className="flex gap-2">
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={handleUpgradeSubscribe}
                      className="flex-1 py-3 rounded-[14px] text-white text-[13px] font-bold"
                      style={{ background: 'linear-gradient(135deg, #6C47FF, #FF2D78)' }}
                    >
                      Subscribe →
                    </motion.button>
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={handleUpgradeUseCredits}
                      disabled={userCredits < (upgradeMode.credits_for_user ?? upgradeMode.credits)}
                      className={`flex-1 py-3 rounded-[14px] text-[13px] font-bold border-2 transition-opacity ${
                        userCredits >= (upgradeMode.credits_for_user ?? upgradeMode.credits)
                          ? 'border-[#6C47FF] text-[#6C47FF]'
                          : 'border-[#D1D1D6] text-[#6E6E73] opacity-50'
                      }`}
                    >
                      Use {upgradeMode.credits_for_user ?? upgradeMode.credits}⚡
                    </motion.button>
                  </div>
                  <button
                    onClick={() => setUpgradeMode(null)}
                    className="w-full text-center text-[12px] text-[#6E6E73] py-1"
                  >
                    ← Back to styles
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="confirm"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="px-4 pb-safe pt-3 border-t border-black/[0.06]"
                >
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={handleConfirm}
                    disabled={selected === 'custom' && !customDesc.trim()}
                    className={`w-full py-4 rounded-[16px] text-white text-[16px] font-semibold transition-opacity ${
                      selected === 'custom' && !customDesc.trim() ? 'opacity-40' : ''
                    }`}
                    style={{ background: 'linear-gradient(135deg, #6C47FF 0%, #FF2D78 100%)' }}
                  >
                    {selectedMode
                      ? `Set ${selectedMode.label} · ${selectedMode.credits_for_user ?? selectedMode.credits}⚡`
                      : 'Set Style'}
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
