import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Flame, Grid2X2, Diamond, Check, Download } from 'lucide-react'
import { SelfieUploader } from '../components/studio/SelfieUploader'
import { ModeSelector } from '../components/studio/ModeSelector'
import { GenerateButton } from '../components/studio/GenerateButton'
import { ProgressRing } from '../components/studio/ProgressRing'
import { ResultCard } from '../components/studio/ResultCard'
import { CreditBadge } from '../components/layout/CreditBadge'
import { PhotoshootModePicker } from '../components/studio/PhotoshootModePicker'
import { PaywallModal } from '../components/studio/PaywallModal'
import { useAppStore } from '../store/appStore'
import { useJobPoller } from '../hooks/useJob'
import { createGeneration, createBatch, getGeneration, requestHD } from '../api/generations'
import { fetchPhotoshootModes, getCachedModes, setCachedModes } from '../api/photoshootModes'
import { getChallenge } from '../api/session'
import { track } from '../api/analytics'
import { useToast } from '../hooks/useToast'
import type { Generation, PhotoshootMode } from '../types'

const tg = window.Telegram?.WebApp

export default function Studio() {
  const { selfieB64, selfiePreview, activePreset, mode, hdEnabled, batchEnabled,
    toggleHd, toggleBatch, currentJob, setCurrentJob, batchJobs, setBatchJobs,
    photoshootMode, setPhotoshootMode, customDesc, setCustomDesc } = useAppStore()

  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [stepLabel, setStepLabel] = useState<string | undefined>(undefined)
  const [progressStep, setProgressStep] = useState(0)
  const [pollingJobId, setPollingJobId] = useState<string | null>(null)
  const [hdLoading, setHdLoading] = useState(false)
  const [batchIndex, setBatchIndex] = useState(0)
  const [referralNudgeDismissed, setReferralNudgeDismissed] = useState(false)
  const [showModePicker, setShowModePicker] = useState(false)
  const [photoshootModes, setPhotoshootModes] = useState<PhotoshootMode[]>([])
  const [showPaywall, setShowPaywall] = useState(false)
  const toast = useToast()

  const user = useAppStore((s) => s.user)
  const streak = user?.streak ?? 0
  const challenge = useAppStore((s) => s.challenge)
  const challengeLoaded = useAppStore((s) => s.challengeLoaded)

  useEffect(() => {
    if (!challengeLoaded) {
      useAppStore.getState().setChallengeLoaded(true)
      getChallenge()
        .then((c) => useAppStore.getState().setChallenge(c))
        .catch(() => null)
    }
  }, [])

  useEffect(() => {
    const cached = getCachedModes()
    if (cached?.length) { setPhotoshootModes(cached); return }
    fetchPhotoshootModes()
      .then(({ modes }) => { setPhotoshootModes(modes); setCachedModes(modes) })
      .catch(() => null)
  }, [])

  useEffect(() => {
    if (activePreset) setPrompt('')
  }, [activePreset])

  const modeConfig = photoshootModes.find((m) => m.key === photoshootMode)
  const baseCost = modeConfig?.credits ?? (photoshootMode === 'everyday' ? 1 : 1)
  const cost = batchEnabled ? 3 : baseCost

  function isJobDone(job: Generation) {
    return job.status === 'done' || job.status === 'ready'
  }

  useJobPoller(pollingJobId, (job) => {
    setCurrentJob(job)

    // Update progress label from backend step_label
    if (job.step_label) setStepLabel(job.step_label)
    if (job.status === 'processing' || job.status === 'running') {
      setProgressStep((s) => Math.min(s + 1, 3))
    }

    if (isJobDone(job) || job.status === 'error' || job.status === 'failed') {
      setLoading(false)
      setPollingJobId(null)
      setProgressStep(0)

      if (isJobDone(job)) {
        tg?.HapticFeedback?.notificationOccurred('success')

        // Variable reward toast
        const jobAny = job as Generation & { bonus_credits?: number }
        if (jobAny.bonus_credits && jobAny.bonus_credits > 0) {
          toast.reward(`🎉 Bonus! +${jobAny.bonus_credits} free credits`, { sub: 'Lucky you — keep creating!' })
        }

        // Handle multiple output_urls (tournament results)
        if (job.output_urls && job.output_urls.length > 1) {
          const pseudoJobs: Generation[] = job.output_urls.map((url, i) => ({
            ...job,
            job_id: `${job.job_id}_r${i}`,
            output_url: url,
          }))
          setBatchJobs(pseudoJobs)
          setBatchIndex(0)
          setCurrentJob(pseudoJobs[0])
        }

        if (job.output_url) {
          useAppStore.getState().prependGallery(job)
        }

        // Proactive paywall: show right after result if credits just ran out
        const credits = useAppStore.getState().user?.credits ?? 1
        if (credits <= 0) {
          setTimeout(() => setShowPaywall(true), 1800) // let user see result first
        }
      }
    }
  })

  async function generate() {
    if (!selfieB64) return
    tg?.HapticFeedback?.impactOccurred('medium')
    track('generate_tapped', { mode: photoshootMode, has_preset: !!activePreset, batch: batchEnabled })
    setLoading(true)
    setCurrentJob(null)
    setBatchJobs([])
    setProgressStep(0)
    setStepLabel('analyzing')

    try {
      const baseParams = {
        image_b64: selfieB64,
        prompt: activePreset?.prompt ?? prompt,
        preset_key: activePreset?.key,
        mode,
        photoshoot_mode: photoshootMode,
        custom_desc: photoshootMode === 'custom' ? customDesc : undefined,
      }

      if (batchEnabled) {
        const { job_ids } = await createBatch(baseParams)
        const jobs = await Promise.all(job_ids.map((id) => getGeneration(id)))
        setBatchJobs(jobs)
        setPollingJobId(job_ids[0])
      } else {
        const { job_id } = await createGeneration(baseParams)
        setPollingJobId(job_id)
      }
    } catch (e: unknown) {
      setLoading(false)
      setProgressStep(0)
      setStepLabel(undefined)
      tg?.HapticFeedback?.notificationOccurred('error')
      // 402 = no credits — show paywall instead of alert
      if ((e as { status?: number })?.status === 402) {
        track('paywall_shown', { trigger: 'blocked', source: 'webapp' })
        setShowPaywall(true)
        return
      }
      toast.error(e instanceof Error ? e.message : 'Generation failed')
    }
  }

  function handleReferralNudge() {
    tg?.HapticFeedback?.impactOccurred('medium')
    track('referral_nudge_tapped', { source: 'post_generation' })
    setReferralNudgeDismissed(true)
    const botLink = user?.bot_link ?? 'https://t.me/imodelapp_bot'
    const shareText = encodeURIComponent('I made this with AI in seconds 🤩 Try it free →')
    const shareUrl = encodeURIComponent(botLink)
    tg?.openLink(`https://t.me/share/url?url=${shareUrl}&text=${shareText}`)
  }

  async function handleHD() {
    if (!currentJob) return
    setHdLoading(true)
    try {
      const { job_id } = await requestHD(currentJob.job_id)
      setPollingJobId(job_id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'HD upgrade failed'
      toast.error(msg)
    } finally {
      setHdLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-[22px] font-bold text-[#1D1D1F]">✦ Studio</span>
          {streak >= 3 && (
            <span className="flex items-center gap-0.5 text-[13px] font-semibold text-orange-500">
              <Flame size={14} fill="currentColor" /> {streak}
            </span>
          )}
          {/* Mode pill */}
          <button
            onClick={() => { tg?.HapticFeedback?.impactOccurred('light'); setShowModePicker(true); track('mode_picker_opened', { current_mode: photoshootMode }) }}
            className="flex items-center gap-1 px-2 py-1 rounded-full bg-[#6C47FF]/10 border border-[#6C47FF]/20"
          >
            <span className="text-[11px]">{modeConfig?.emoji ?? '📸'}</span>
            <span className="text-[11px] font-medium text-[#6C47FF]">{modeConfig?.label_en ?? 'Everyday'}</span>
            <span className="text-[9px] text-[#6C47FF]/60">▾</span>
          </button>
        </div>
        <CreditBadge />
      </div>

      <div className="flex-1 px-4 pb-4 space-y-3">
        <SelfieUploader />
        <ModeSelector />

        {/* Streak at risk banner */}
        {user?.last_gen_at && (Date.now() / 1000 - user.last_gen_at) > 20 * 3600 && (user?.streak ?? 0) > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2.5 px-4 py-3 rounded-card bg-orange-50 border border-orange-200"
          >
            <Flame size={18} className="text-orange-500 flex-shrink-0" fill="currentColor" />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-bold text-orange-700">Streak at risk! 🔥 {streak} days</p>
              <p className="text-[11px] text-orange-500">Generate now to keep your streak alive</p>
            </div>
          </motion.div>
        )}

        {/* Daily Challenge Badge */}
        {challenge && (
          <motion.button
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            onClick={() => {
              tg?.HapticFeedback?.impactOccurred('light')
              useAppStore.getState().setActivePreset({
                key: challenge.preset_key,
                label: challenge.label,
                category: 'challenge',
                is_premium: false,
                emoji: '⚡',
              })
            }}
            className="w-full flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-[#FF9500]/10 to-[#FF2D78]/10 border border-[#FF9500]/20 rounded-card"
          >
            <span className="text-2xl">⚡</span>
            <div className="flex-1 text-left">
              <p className="text-[13px] font-semibold text-[#1D1D1F]">Trend today: {challenge.label}</p>
              <div className="flex items-center gap-2">
                <p className="text-[11px] text-[#6E6E73]">+{challenge.bonus_credits} bonus credits</p>
                {challenge.participants_today && (
                  <p className="text-[10px] font-semibold text-[#FF9500]">
                    · {challenge.participants_today} creators today
                  </p>
                )}
              </div>
            </div>
            <span className="text-[12px] font-medium text-[#FF9500]">Try →</span>
          </motion.button>
        )}

        {/* Active preset chip */}
        {activePreset && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 px-3 py-2 bg-[#6C47FF]/10 rounded-pill w-fit"
          >
            <span>{activePreset.emoji}</span>
            <span className="text-[12px] font-medium text-[#6C47FF]">{activePreset.label}</span>
            <button onClick={() => useAppStore.getState().setActivePreset(null)} className="text-[#6C47FF]/60">✕</button>
          </motion.div>
        )}

        {/* Custom mode: vision input */}
        {photoshootMode === 'custom' && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
            <textarea
              value={customDesc}
              onChange={(e) => setCustomDesc(e.target.value)}
              placeholder="Describe your vision... (e.g. CEO portrait in NYC office, summer beach editorial)"
              rows={2}
              className="w-full px-4 py-3 rounded-card bg-[#6C47FF]/5 border border-[#6C47FF]/20 text-[14px] text-[#1D1D1F] placeholder-[#6E6E73] resize-none outline-none"
            />
          </motion.div>
        )}

        {/* Prompt (not for custom mode) */}
        {!activePreset && photoshootMode !== 'custom' && (
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={mode === 'portrait' ? 'Describe your style... (optional)' : mode === 'copy_scene' ? 'Describe the scene to recreate...' : 'Describe the style for face swap...'}
            rows={2}
            className="w-full px-4 py-3 rounded-card bg-[#F5F5F7] text-[14px] text-[#1D1D1F] placeholder-[#6E6E73] resize-none outline-none"
          />
        )}

        {/* Feature toggles (only for everyday) */}
        {photoshootMode === 'everyday' && (
          <div className="flex gap-2">
            <button
              onClick={() => { tg?.HapticFeedback?.impactOccurred('light'); toggleBatch() }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-card text-[12px] font-medium border transition-colors ${
                batchEnabled ? 'bg-[#6C47FF]/10 border-[#6C47FF]/30 text-[#6C47FF]' : 'bg-[#F5F5F7] border-transparent text-[#6E6E73]'
              }`}
            >
              <Grid2X2 size={13} /> Batch ×4 · 3⚡
            </button>
            <button
              onClick={() => { tg?.HapticFeedback?.impactOccurred('light'); toggleHd() }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-card text-[12px] font-medium border transition-colors ${
                hdEnabled ? 'bg-[#6C47FF]/10 border-[#6C47FF]/30 text-[#6C47FF]' : 'bg-[#F5F5F7] border-transparent text-[#6E6E73]'
              }`}
            >
              <Diamond size={13} /> HD · +2⚡
            </button>
          </div>
        )}

        {/* Mode info for non-everyday */}
        {photoshootMode !== 'everyday' && modeConfig && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 px-3 py-2.5 rounded-card bg-[#6C47FF]/5 border border-[#6C47FF]/15"
          >
            <span className="text-[18px]">{modeConfig.emoji}</span>
            <div className="flex-1">
              <span className="text-[12px] text-[#6C47FF] font-medium">{modeConfig.label_en}</span>
              <span className="text-[11px] text-[#6E6E73] ml-1.5">{modeConfig.short_desc}</span>
            </div>
          </motion.div>
        )}

        <GenerateButton onClick={generate} loading={loading && !currentJob} disabled={!selfieB64} cost={cost} />

        {/* Progress */}
        <AnimatePresence>
          {loading && !currentJob && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <ProgressRing step={progressStep} stepLabel={stepLabel} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Multi-result grid (tournament results or batch) */}
        {batchJobs.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[13px] font-semibold text-[#1D1D1F]">
                {photoshootMode !== 'everyday' ? 'Pick your best shot' : 'Tap to select'}
              </p>
              <span className="text-[11px] text-[#6E6E73]">
                {batchJobs.filter(isJobDone).length}/{batchJobs.length} ready
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {batchJobs.map((job, i) => {
                const isDone = isJobDone(job)
                const isActive = batchIndex === i
                return (
                  <motion.button
                    key={job.job_id}
                    whileTap={{ scale: 0.96 }}
                    onClick={() => {
                      if (!isDone) return
                      tg?.HapticFeedback?.impactOccurred('light')
                      setBatchIndex(i)
                      setCurrentJob(job)
                    }}
                    className="relative rounded-card overflow-hidden"
                  >
                    {isDone && job.output_url ? (
                      <img src={job.output_url} alt={`result ${i + 1}`} className="w-full aspect-square object-cover" />
                    ) : (
                      <div className="w-full aspect-square bg-[#F5F5F7] flex items-center justify-center">
                        <div className="w-5 h-5 rounded-full border-2 border-[#6C47FF]/30 border-t-[#6C47FF] animate-spin" />
                      </div>
                    )}
                    {isActive && isDone && (
                      <div className="absolute inset-0 border-[3px] border-[#6C47FF] rounded-card pointer-events-none" />
                    )}
                    {isDone && (
                      <div className={`absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center shadow transition-colors ${
                        isActive ? 'bg-[#6C47FF]' : 'bg-white/80'
                      }`}>
                        {isActive && <Check size={12} className="text-white" strokeWidth={3} />}
                      </div>
                    )}
                  </motion.button>
                )
              })}
            </div>
            {batchJobs.some(isJobDone) && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-2"
              >
                <motion.a
                  whileTap={{ scale: 0.97 }}
                  href={batchJobs[batchIndex]?.output_url ?? '#'}
                  download="imodel-best.jpg"
                  onClick={() => {
                    tg?.HapticFeedback?.notificationOccurred('success')
                    track('batch_keep_best', { index: batchIndex })
                  }}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-card bg-[#6C47FF] text-white text-[13px] font-semibold"
                >
                  <Check size={14} strokeWidth={3} /> Keep best
                </motion.a>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={() => {
                    const readyJobs = batchJobs.filter(j => isJobDone(j) && j.output_url)
                    readyJobs.forEach((job, idx) => {
                      setTimeout(() => {
                        const a = document.createElement('a')
                        a.href = job.output_url!
                        a.download = `imodel-${idx + 1}.jpg`
                        a.click()
                      }, idx * 250)
                    })
                    tg?.HapticFeedback?.notificationOccurred('success')
                    toast.success(`Saving ${readyJobs.length} photos...`)
                    track('batch_save_all', { count: readyJobs.length })
                  }}
                  className="flex items-center justify-center gap-1.5 px-4 py-3 rounded-card bg-[#F5F5F7] text-[#1D1D1F] text-[12px] font-medium"
                >
                  <Download size={13} />
                  All ({batchJobs.filter(isJobDone).length})
                </motion.button>
              </motion.div>
            )}
          </div>
        )}

        {/* Single result */}
        {currentJob && isJobDone(currentJob) && !batchJobs.length && (
          <ResultCard
            job={currentJob}
            beforeUrl={selfiePreview ?? undefined}
            onRegenerate={generate}
            onHD={handleHD}
            hdLoading={hdLoading}
          />
        )}

        {/* Post-generation referral nudge */}
        {currentJob && isJobDone(currentJob) && !batchJobs.length && !referralNudgeDismissed && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.8, type: 'spring', stiffness: 300, damping: 28 }}
            className="flex items-center gap-3 px-4 py-3 rounded-card bg-gradient-to-r from-[#34C759]/10 to-[#30D158]/10 border border-[#34C759]/20"
          >
            <span className="text-[22px]">🎁</span>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-semibold text-[#1D1D1F]">Share → get +3 free credits</p>
              <p className="text-[11px] text-[#6E6E73]">Invite a friend, you both earn</p>
            </div>
            <div className="flex flex-col items-end gap-1.5">
              <button
                onClick={handleReferralNudge}
                className="px-3 py-1.5 rounded-full bg-[#34C759] text-white text-[11px] font-bold"
              >
                Invite
              </button>
              <button
                onClick={() => setReferralNudgeDismissed(true)}
                className="text-[10px] text-[#6E6E73]"
              >
                Later
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {/* Mode picker modal */}
      <PhotoshootModePicker
        open={showModePicker}
        onClose={() => setShowModePicker(false)}
        onSelect={(newMode, desc) => {
          setPhotoshootMode(newMode)
          if (desc) setCustomDesc(desc)
          setShowModePicker(false)
        }}
        currentMode={photoshootMode}
        userCredits={user?.credits ?? 0}
        modes={photoshootModes}
      />

      {/* Paywall modal */}
      <AnimatePresence>
        {showPaywall && (
          <PaywallModal
            lastResultUrl={currentJob?.output_url ?? undefined}
            onClose={() => setShowPaywall(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
