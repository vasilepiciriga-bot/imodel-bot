import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Flame, Grid2X2, Diamond } from 'lucide-react'
import { SelfieUploader } from '../components/studio/SelfieUploader'
import { ModeSelector } from '../components/studio/ModeSelector'
import { GenerateButton } from '../components/studio/GenerateButton'
import { ProgressRing } from '../components/studio/ProgressRing'
import { ResultCard } from '../components/studio/ResultCard'
import { CreditBadge } from '../components/layout/CreditBadge'
import { useAppStore } from '../store/appStore'
import { useJobPoller } from '../hooks/useJob'
import { createGeneration, createBatch, getGeneration, requestHD } from '../api/generations'
import { getChallenge } from '../api/session'
import type { Challenge } from '../types'

const tg = window.Telegram?.WebApp

export default function Studio() {
  const { selfieB64, selfiePreview, activePreset, mode, hdEnabled, batchEnabled,
    toggleHd, toggleBatch, currentJob, setCurrentJob, batchJobs, setBatchJobs,
    updateCredits } = useAppStore()

  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [pollingJobId, setPollingJobId] = useState<string | null>(null)
  const [hdLoading, setHdLoading] = useState(false)
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [batchIndex, setBatchIndex] = useState(0)

  const user = useAppStore((s) => s.user)
  const streak = user?.streak ?? 0

  useEffect(() => {
    getChallenge().then(setChallenge).catch(() => null)
  }, [])

  useEffect(() => {
    if (activePreset) setPrompt('')
  }, [activePreset])

  const cost = batchEnabled ? 3 : hdEnabled ? 3 : 1

  useJobPoller(pollingJobId, (job) => {
    setCurrentJob(job)
    if (job.status === 'processing') setProgressStep((s) => Math.min(s + 1, 3))
    if (job.status === 'done' || job.status === 'error') {
      setLoading(false)
      setPollingJobId(null)
      setProgressStep(0)
      if (job.status === 'done') {
        tg?.HapticFeedback?.notificationOccurred('success')
        if (job.output_url) {
          useAppStore.getState().prependGallery(job)
        }
      }
    }
  })

  async function generate() {
    if (!selfieB64) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setLoading(true)
    setCurrentJob(null)
    setBatchJobs([])
    setProgressStep(1)

    try {
      const params = {
        selfie_b64: selfieB64,
        prompt: activePreset?.prompt ?? prompt,
        preset_key: activePreset?.key,
        mode,
      }

      if (batchEnabled) {
        const { job_ids } = await createBatch(params)
        const jobs = await Promise.all(job_ids.map((id) => getGeneration(id)))
        setBatchJobs(jobs)
        setPollingJobId(job_ids[0])
      } else {
        const { job_id } = await createGeneration(params)
        setPollingJobId(job_id)
      }
    } catch (e: unknown) {
      setLoading(false)
      setProgressStep(0)
      const msg = e instanceof Error ? e.message : 'Generation failed'
      tg?.HapticFeedback?.notificationOccurred('error')
      alert(msg)
    }
  }

  async function handleHD() {
    if (!currentJob) return
    setHdLoading(true)
    try {
      const { job_id } = await requestHD(currentJob.job_id)
      setPollingJobId(job_id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'HD failed'
      alert(msg)
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
        </div>
        <CreditBadge />
      </div>

      <div className="flex-1 px-4 pb-4 space-y-3">
        <SelfieUploader />
        <ModeSelector />

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
              <p className="text-[11px] text-[#6E6E73]">+{challenge.bonus_credits} bonus credits</p>
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

        {/* Prompt */}
        {!activePreset && (
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={mode === 'portrait' ? 'Describe your style... (optional)' : mode === 'copy_scene' ? 'Describe the scene to recreate...' : 'Describe the style for face swap...'}
            rows={2}
            className="w-full px-4 py-3 rounded-card bg-[#F5F5F7] text-[14px] text-[#1D1D1F] placeholder-[#6E6E73] resize-none outline-none"
          />
        )}

        {/* Feature toggles */}
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

        <GenerateButton onClick={generate} loading={loading && !currentJob} disabled={!selfieB64} cost={cost} />

        {/* Progress */}
        <AnimatePresence>
          {loading && !currentJob && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <ProgressRing step={progressStep} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Batch results */}
        {batchJobs.length > 0 && (
          <div className="space-y-2">
            <p className="text-[12px] text-[#6E6E73] font-medium">Tap to select</p>
            <div className="grid grid-cols-2 gap-2">
              {batchJobs.map((job, i) => (
                <motion.button
                  key={job.job_id}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => { setBatchIndex(i); setCurrentJob(job) }}
                  className={`rounded-card overflow-hidden border-2 ${batchIndex === i ? 'border-[#6C47FF]' : 'border-transparent'}`}
                >
                  {job.output_url ? (
                    <img src={job.output_url} alt={`batch ${i + 1}`} className="w-full aspect-square object-cover" />
                  ) : (
                    <div className="w-full aspect-square bg-gray-100 flex items-center justify-center">
                      <span className="text-[#6E6E73] text-[11px]">{job.status}</span>
                    </div>
                  )}
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {/* Single result */}
        {currentJob?.status === 'done' && !batchJobs.length && (
          <ResultCard
            job={currentJob}
            beforeUrl={selfiePreview ?? undefined}
            onRegenerate={generate}
            onHD={handleHD}
            hdLoading={hdLoading}
          />
        )}
      </div>
    </div>
  )
}
