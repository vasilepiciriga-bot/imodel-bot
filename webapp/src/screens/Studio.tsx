import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Flame, Grid2X2, Diamond, Check, Download, Upload, Zap } from 'lucide-react'
import confetti from 'canvas-confetti'
import { SelfieUploader } from '../components/studio/SelfieUploader'
import { ModeSelector } from '../components/studio/ModeSelector'
import { GenerateButton } from '../components/studio/GenerateButton'
import { ProgressRing } from '../components/studio/ProgressRing'
import { GeneratingCard } from '../components/studio/GeneratingCard'
import { ResultCard } from '../components/studio/ResultCard'
import { CreditBadge } from '../components/layout/CreditBadge'
import { PhotoshootModePicker } from '../components/studio/PhotoshootModePicker'
import { PaywallModal } from '../components/studio/PaywallModal'
import { FirstGenModal } from '../components/shared/FirstGenModal'
import { useAppStore } from '../store/appStore'
import { useJobPoller } from '../hooks/useJob'
import { createGeneration, createBatch, getGeneration, requestHD } from '../api/generations'
import { fetchPhotoshootModes, getCachedModes, setCachedModes } from '../api/photoshootModes'
import { getChallenge, claimDaily, getMe } from '../api/session'
import { getLeaderboard, type LeaderboardData } from '../api/leaderboard'
import { getQuests, claimQuest, type QuestItem } from '../api/quests'
import { getCachedPresets } from '../api/presets'
import { getCommunityPresets } from '../api/community'
import type { Preset } from '../types'
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
  const [showFirstGen, setShowFirstGen] = useState(false)
  const [firstGenUrl, setFirstGenUrl] = useState('')
  const [refUrl, setRefUrl] = useState('')
  const [refB64, setRefB64] = useState<string | null>(null)
  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [refLoading, setRefLoading] = useState(false)
  const [claimingDaily, setClaimingDaily] = useState(false)
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null)
  const [claimableQuest, setClaimableQuest] = useState<QuestItem | null>(null)
  const [claimingQuest, setClaimingQuest] = useState(false)
  const [recentPresets, setRecentPresets] = useState<Preset[]>([])
  const [communityInspiration, setCommunityInspiration] = useState<Preset[]>([])
  const toast = useToast()

  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const updateCredits = useAppStore((s) => s.updateCredits)
  const streak = user?.streak ?? 0

  const handleClaimDaily = useCallback(async () => {
    if (claimingDaily) return
    setClaimingDaily(true)
    tg?.HapticFeedback?.impactOccurred('medium')
    try {
      const result = await claimDaily()
      confetti({ particleCount: result.milestone_bonus ? 140 : 60, spread: result.milestone_bonus ? 90 : 60, origin: { y: 0.5 }, colors: ['#6C47FF', '#FF2D78', '#FFD700', '#34C759'] })
      tg?.HapticFeedback?.notificationOccurred('success')
      if (result.milestone_bonus) {
        toast.success(`🔥 Day ${result.streak} streak! +${result.gens_added}⚡ milestone bonus!`, { icon: '🏆' })
      } else if ((result.phase ?? 0) >= 2) {
        toast.success(`+${result.gens_added}⚡ claimed! 💜 Subscribers always get +2/day`, { icon: '🎁', duration: 4000 })
      } else {
        toast.success(`+${result.gens_added}⚡ daily bonus claimed!`, { icon: '🎁' })
      }
      const updated = await getMe()
      setUser(updated)
      updateCredits(updated.credits)
    } catch {
      toast.error('Already claimed today')
    } finally {
      setClaimingDaily(false)
    }
  }, [claimingDaily, setUser, updateCredits, toast])
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
    const cached = sessionStorage.getItem('imodel_lb')
    const cachedAt = parseInt(sessionStorage.getItem('imodel_lb_at') ?? '0')
    if (cached && Date.now() - cachedAt < 5 * 60 * 1000) {
      setLeaderboard(JSON.parse(cached))
    } else {
      getLeaderboard().then((lb) => {
        setLeaderboard(lb)
        sessionStorage.setItem('imodel_lb', JSON.stringify(lb))
        sessionStorage.setItem('imodel_lb_at', String(Date.now()))
      }).catch(() => null)
    }
  }, [])

  // Build "Continue where you left off" strip from user's style history
  useEffect(() => {
    if (!user?.recent_presets?.length) return
    const cached = getCachedPresets()
    if (!cached?.length) return
    const picks = user.recent_presets
      .map((key) => cached.find((p) => p.key === key))
      .filter((p): p is Preset => p != null)
      .slice(0, 3)
    setRecentPresets(picks)
  }, [user?.recent_presets])

  useEffect(() => {
    if (activePreset) setPrompt('')
  }, [activePreset])

  useEffect(() => {
    if (mode !== 'copy_image') {
      setRefB64(null)
      setRefPreview(null)
      setRefUrl('')
    }
  }, [mode])

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

        // First-generation celebration (only once ever)
        const freshUser = useAppStore.getState().user
        const celebrated = localStorage.getItem('imodel_first_gen_celebrated')
        if (!celebrated && (freshUser?.gens_ok ?? 0) === 1 && job.output_url) {
          localStorage.setItem('imodel_first_gen_celebrated', '1')
          setFirstGenUrl(job.output_url)
          setTimeout(() => setShowFirstGen(true), 800)
        }

        // Check for newly claimable quests after generation
        getQuests().then(({ quests }) => {
          const claimable = quests.find((q) => q.claimable)
          setClaimableQuest(claimable ?? null)
        }).catch(() => null)

        // Fetch top-3 community photos for inspiration (after job done, fire-and-forget)
        if (communityInspiration.length === 0) {
          getCommunityPresets('top').then(({ presets }) => {
            setCommunityInspiration(presets.filter((p) => p.thumbnail_url).slice(0, 3))
          }).catch(() => null)
        }

        // Proactive paywall: show right after result if credits just ran out
        const credits = useAppStore.getState().user?.credits ?? 1
        if (credits <= 0) {
          setTimeout(() => setShowPaywall(true), 1800) // let user see result first
        }
      } else {
        const errMsg = job.error === 'selfie_quality' ? 'Photo rejected — try a clearer selfie'
          : job.error === 'blocked' ? 'Content blocked. Try a different style.'
          : job.error === 'no_credits' ? 'Not enough credits'
          : 'Generation failed — tap Generate to retry'
        toast.error(errMsg)
        tg?.HapticFeedback?.notificationOccurred('error')
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
        mode: mode === 'copy_image' ? 'copy_scene' : mode,
        style_b64: mode === 'copy_image' ? (refB64 ?? undefined) : undefined,
        // copy_image must go through the everyday path — tournament job drops style_bytes
        photoshoot_mode: mode === 'copy_image' ? 'everyday' : photoshootMode,
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

  const generateWithMode = useCallback(async (modeKey: string) => {
    if (!selfieB64 || loading) return
    tg?.HapticFeedback?.impactOccurred('medium')
    setLoading(true)
    setCurrentJob(null)
    setBatchJobs([])
    setProgressStep(0)
    setStepLabel('analyzing')
    track('upsell_mode_generate', { mode: modeKey })
    try {
      const { job_id } = await createGeneration({
        image_b64: selfieB64,
        photoshoot_mode: modeKey,
        prompt: activePreset?.prompt ?? prompt,
        preset_key: activePreset?.key,
      })
      setPhotoshootMode(modeKey as import('../types').PhotoshootModeKey)
      setPollingJobId(job_id)
    } catch (e: unknown) {
      setLoading(false)
      setProgressStep(0)
      setStepLabel(undefined)
      if ((e as { status?: number })?.status === 402) {
        track('paywall_shown', { trigger: 'upsell_mode', source: 'result_card' })
        setShowPaywall(true)
      } else {
        toast.error(e instanceof Error ? e.message : 'Generation failed')
      }
    }
  }, [selfieB64, loading, prompt, activePreset, setPhotoshootMode])

  async function handleQuestClaim(questId: string) {
    setClaimingQuest(true)
    try {
      const result = await claimQuest(questId)
      if (result.new_balance !== undefined) useAppStore.getState().updateCredits(result.new_balance)
      toast.reward(`⚡ +${result.credits_added ?? '?'} credits claimed!`, { sub: 'Keep generating to unlock more' })
      setClaimableQuest(null)
    } catch {
      toast.error('Could not claim quest')
    } finally {
      setClaimingQuest(false)
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

  async function loadRefFromUrl() {
    if (!refUrl.trim()) return
    setRefLoading(true)
    tg?.HapticFeedback?.impactOccurred('light')
    try {
      const proxyUrl = `/api/v1/proxy-image?url=${encodeURIComponent(refUrl.trim())}`
      const res = await fetch(proxyUrl, {
        headers: { Authorization: `tma ${(tg as unknown as { initData?: string })?.initData ?? ''}` },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        if ((body as { error?: string }).error === 'not_an_image') throw new Error('not_an_image')
        throw new Error('proxy ' + res.status)
      }
      const blob = await res.blob()
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = reject
        reader.readAsDataURL(blob)
      })
      setRefPreview(dataUrl)
      setRefB64(dataUrl.split(',')[1])
    } catch (e) {
      if (e instanceof Error && e.message === 'not_an_image') {
        toast.error('Это не прямая ссылка на фото — нажми на фото → «Копировать адрес изображения»')
      } else {
        toast.error('Не удалось загрузить изображение')
      }
    } finally {
      setRefLoading(false)
    }
  }

  function handleRefFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setRefLoading(true)
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      setRefPreview(dataUrl)
      setRefB64(dataUrl.split(',')[1])
      setRefLoading(false)
    }
    reader.onerror = () => {
      toast.error('Ошибка загрузки файла')
      setRefLoading(false)
    }
    reader.readAsDataURL(file)
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

      {/* Daily bonus ready pill */}
      <AnimatePresence>
        {user?.can_claim_daily && (
          <motion.button
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            onClick={handleClaimDaily}
            disabled={claimingDaily}
            className="mx-4 mb-1 flex items-center gap-2 px-4 py-2.5 rounded-[14px] bg-gradient-to-r from-[#34C759]/15 to-[#34C759]/5 border border-[#34C759]/30 disabled:opacity-60"
          >
            <motion.span
              animate={{ scale: [1, 1.15, 1] }}
              transition={{ repeat: Infinity, duration: 1.8 }}
              className="text-[18px]"
            >🎁</motion.span>
            <div className="flex-1 text-left">
              <span className="text-[13px] font-semibold text-[#1D1D1F]">
                {claimingDaily ? 'Claiming…' : `Daily bonus ready! +${user.next_daily_credits ?? 1}⚡`}
              </span>
            </div>
            <span className="text-[12px] text-[#34C759] font-semibold">Claim →</span>
          </motion.button>
        )}
      </AnimatePresence>

      <div className="flex-1 px-4 pb-4 space-y-3">
        {/* Leaderboard strip */}
        <AnimatePresence>
          {leaderboard && leaderboard.entries.length >= 2 && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-[#F5F5F7]"
            >
              <span className="text-[11px]">🏆</span>
              {leaderboard.entries.slice(0, 2).map((e) => (
                <span key={e.rank} className="text-[11px] text-[#1D1D1F] font-medium truncate max-w-[80px]">
                  {e.display_name} · {e.gens}
                </span>
              ))}
              {leaderboard.my_rank && (
                <span className="text-[11px] text-[#6E6E73] ml-auto shrink-0">You: #{leaderboard.my_rank}</span>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* "Continue where you left off" recent presets strip */}
        <AnimatePresence>
          {recentPresets.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <p className="text-[11px] font-semibold text-[#6E6E73] mb-1.5 px-0.5">Continue where you left off</p>
              <div className="flex gap-2">
                {recentPresets.map((p) => (
                  <motion.button
                    key={p.key}
                    whileTap={{ scale: 0.93 }}
                    onClick={() => {
                      useAppStore.getState().setActivePreset(p)
                      track('recent_preset_tapped', { key: p.key })
                    }}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border text-[11px] font-semibold transition-colors ${
                      activePreset?.key === p.key
                        ? 'bg-[#6C47FF] border-[#6C47FF] text-white'
                        : 'bg-white border-[#E0E0E5] text-[#1D1D1F]'
                    }`}
                  >
                    <span>{p.emoji}</span>
                    <span className="truncate max-w-[60px]">{p.label}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <SelfieUploader />
        <ModeSelector />

        {/* Copy Image reference panel */}
        <AnimatePresence mode="wait">
          {mode === 'copy_image' && (
            <motion.div
              key="copy-image-panel"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="rounded-card bg-[#F5F5F7] p-4 space-y-3"
            >
              <div>
                <p className="text-[13px] font-semibold text-[#1D1D1F]">📎 Референс-фото</p>
                <p className="text-[11px] text-[#6E6E73] mt-0.5">Загрузи фото образа, который хочешь повторить</p>
              </div>

              {refPreview ? (
                <div className="relative rounded-[12px] overflow-hidden" style={{ aspectRatio: '1/1', maxHeight: 180 }}>
                  <img src={refPreview} alt="reference" className="w-full h-full object-cover" />
                  <button
                    onClick={() => { setRefPreview(null); setRefB64(null); setRefUrl('') }}
                    className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 flex items-center justify-center text-white text-[12px] font-bold"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={refUrl}
                      onChange={(e) => setRefUrl(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); loadRefFromUrl() } }}
                      placeholder="Вставь ссылку (Pinterest, Instagram…)"
                      className="flex-1 px-3 py-2.5 rounded-[10px] bg-white border border-[#E5E5EA] text-[13px] text-[#1D1D1F] placeholder-[#C7C7CC] outline-none focus:border-[#6C47FF]/40"
                    />
                    <button
                      onClick={loadRefFromUrl}
                      disabled={!refUrl.trim() || refLoading}
                      className="px-3.5 py-2.5 rounded-[10px] bg-[#6C47FF] text-white text-[12px] font-semibold disabled:opacity-40 min-w-[44px] flex items-center justify-center"
                    >
                      {refLoading ? <span className="animate-pulse">…</span> : <Download size={14} />}
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-px bg-[#E5E5EA]" />
                    <span className="text-[11px] text-[#AEAEB2]">или</span>
                    <div className="flex-1 h-px bg-[#E5E5EA]" />
                  </div>

                  <label
                    htmlFor="ref-upload"
                    className="flex items-center justify-center gap-2 py-2.5 rounded-[10px] bg-white border border-[#E5E5EA] text-[13px] font-medium text-[#1D1D1F] cursor-pointer active:bg-[#F5F5F7]"
                  >
                    <Upload size={14} className="text-[#6C47FF]" />
                    Загрузить с телефона
                  </label>
                  <input
                    id="ref-upload"
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleRefFile}
                  />
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Streak at risk banner */}
        {user?.last_gen_at && (Date.now() / 1000 - user.last_gen_at) > 18 * 3600 && streak >= 3 && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2.5 px-4 py-3 rounded-card bg-orange-50 border border-orange-200"
          >
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
            >
              <Flame size={20} className="text-orange-500 flex-shrink-0" fill="currentColor" />
            </motion.div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-bold text-orange-700">🔥 {streak}-day streak at risk!</p>
              <p className="text-[11px] text-orange-500">Generate now to keep it alive</p>
            </div>
            {selfieB64 && (
              <button
                onClick={() => generate()}
                className="px-3 py-1.5 rounded-[10px] bg-orange-500 text-white text-[11px] font-bold flex-shrink-0"
              >
                Generate →
              </button>
            )}
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

        {/* Prompt (not for custom mode or copy_image) */}
        {!activePreset && photoshootMode !== 'custom' && mode !== 'copy_image' && (
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

        {/* Low-credit soft upsell banner */}
        {(user?.credits ?? 0) > 0 && (user?.credits ?? 0) <= 3 && (user?.gens_ok ?? 0) >= 1 && (
          <motion.button
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: [0, 1] }}
            onClick={() => setShowPaywall(true)}
            className="w-full flex items-center gap-2.5 px-4 py-3 rounded-[14px] bg-amber-50 border border-amber-300"
          >
            <motion.div
              animate={{ opacity: [0.6, 1, 0.6] }}
              transition={{ repeat: Infinity, duration: 1.6 }}
            >
              <Zap size={16} className="text-amber-500" fill="currentColor" />
            </motion.div>
            <span className="flex-1 text-left text-[13px] font-semibold text-amber-700">
              Only {user?.credits} gen{user?.credits === 1 ? '' : 's'} left · Top up →
            </span>
          </motion.button>
        )}

        <GenerateButton onClick={generate} loading={loading && (!currentJob || !isJobDone(currentJob))} disabled={!selfieB64 || (mode === 'copy_image' && !refB64)} cost={cost} />

        {/* Progress */}
        <AnimatePresence>
          {loading && (!currentJob || !isJobDone(currentJob)) && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              {selfiePreview
                ? <GeneratingCard selfiePreview={selfiePreview} stepLabel={stepLabel} step={progressStep} />
                : <ProgressRing step={progressStep} stepLabel={stepLabel} />}
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
            photoshootMode={currentJob.photoshoot_mode ?? photoshootMode}
            onTryMode={generateWithMode}
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

        {/* Inline quest completion card */}
        <AnimatePresence>
          {claimableQuest && currentJob && isJobDone(currentJob) && !batchJobs.length && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ delay: 2.2, type: 'spring', stiffness: 300, damping: 28 }}
              className="flex items-center gap-3 px-4 py-3 rounded-card bg-gradient-to-r from-[#6C47FF]/10 to-[#FF2D78]/10 border border-[#6C47FF]/20"
            >
              <span className="text-[22px]">⚡</span>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-[#1D1D1F]">Quest complete: {claimableQuest.title}</p>
                <p className="text-[11px] text-[#6E6E73]">+{claimableQuest.reward}⚡ waiting for you</p>
              </div>
              <button
                onClick={() => handleQuestClaim(claimableQuest.id)}
                disabled={claimingQuest}
                className="px-3 py-1.5 rounded-full bg-[#6C47FF] text-white text-[11px] font-bold disabled:opacity-60 shrink-0"
              >
                {claimingQuest ? '…' : 'Claim now'}
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Community inspiration strip — shown after first generation */}
        <AnimatePresence>
          {communityInspiration.length > 0 && currentJob && isJobDone(currentJob) && !batchJobs.length && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ delay: 0.6 }}
            >
              <p className="text-[11px] font-semibold text-[#6E6E73] mb-1.5 px-0.5">Community Gallery picks</p>
              <div className="flex gap-2.5">
                {communityInspiration.map((p) => (
                  <motion.button
                    key={p.key}
                    whileTap={{ scale: 0.94 }}
                    onClick={() => {
                      useAppStore.getState().setActivePreset(p)
                      track('community_inspiration_tapped', { key: p.key })
                    }}
                    className="flex-1 flex flex-col items-center gap-1"
                  >
                    <div className="w-full aspect-square rounded-[12px] overflow-hidden bg-[#E8E8ED]">
                      {p.thumbnail_url && (
                        <img src={p.thumbnail_url} alt={p.label} className="w-full h-full object-cover" />
                      )}
                    </div>
                    <span className="text-[9px] text-[#6E6E73] truncate w-full text-center">{p.label}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
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
        onUpgrade={() => setShowPaywall(true)}
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

      {/* First-generation celebration modal */}
      <AnimatePresence>
        {showFirstGen && (
          <FirstGenModal
            resultUrl={firstGenUrl}
            onClose={() => setShowFirstGen(false)}
            onUpgrade={() => { setShowFirstGen(false); setShowPaywall(true) }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
