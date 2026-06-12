import { useState, useEffect, useCallback, useRef } from 'react'
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
import { LeaderboardModal } from '../components/shared/LeaderboardModal'
import { useAppStore } from '../store/appStore'
import { useJobPoller } from '../hooks/useJob'
import { createGeneration, createBatch, getGeneration, requestHD } from '../api/generations'
import { fetchPhotoshootModes, getCachedModes, setCachedModes } from '../api/photoshootModes'
import { getChallenge, claimDaily, getMeFresh, getIdentityPassport } from '../api/session'
import { getLeaderboard, getMonthlyChallenge, type LeaderboardData, type MonthlyChallenge } from '../api/leaderboard'
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
  const [questPillDismissedFor, setQuestPillDismissedFor] = useState<string | null>(null)
  const [recentPresets, setRecentPresets] = useState<Preset[]>([])
  const [communityInspiration, setCommunityInspiration] = useState<Preset[]>([])
  const [styleVariant, setStyleVariant] = useState<string>('')
  const [identityPassport, setIdentityPassport] = useState<import('../types').IdentityPassport | null>(null)
  const [showStreakModal, setShowStreakModal] = useState(false)
  const [showLeaderboard, setShowLeaderboard] = useState(false)
  const [monthlyChallenge, setMonthlyChallenge] = useState<MonthlyChallenge | null>(null)
  const [challengeDismissed, setChallengeDismissed] = useState(false)
  const [showReferralNudge, setShowReferralNudge] = useState(false)
  const pseudoStepTimers = useRef<ReturnType<typeof setTimeout>[]>([])
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
      const updated = await getMeFresh()
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

  // Monthly challenge
  useEffect(() => {
    getMonthlyChallenge().then((c) => { if (c.active) setMonthlyChallenge(c) }).catch(() => null)
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

  // Streak-at-risk modal: show 3s after app open (not instantly) when risk conditions met
  useEffect(() => {
    if (!user?.last_gen_at || (user.streak ?? 0) < 3) return
    const hoursSince = (Date.now() / 1000 - user.last_gen_at) / 3600
    if (hoursSince < 18) return
    const snoozedAt = Number(localStorage.getItem('streak_risk_snoozed') ?? 0)
    if (Date.now() - snoozedAt < 2 * 60 * 60 * 1000) return
    const t = setTimeout(() => {
      setShowStreakModal(true)
      track('streak_at_risk_modal_shown', { streak: user.streak })
    }, 3000)
    return () => clearTimeout(t)
  }, [user?.last_gen_at, user?.streak])

  // Fetch claimable quests on mount (complements post-generation fetch)
  useEffect(() => {
    getQuests().then(({ quests }) => {
      const claimable = quests.find((q) => q.claimable)
      setClaimableQuest(claimable ?? null)
    }).catch(() => null)
  }, [])

  const modeConfig = photoshootModes.find((m) => m.key === photoshootMode)
  const baseCost = modeConfig?.credits_for_user ?? modeConfig?.credits ?? (photoshootMode === 'everyday' ? 1 : 1)
  const cost = batchEnabled ? 3 : baseCost

  function isJobDone(job: Generation) {
    return job.status === 'done' || job.status === 'ready'
  }

  // Client-side pseudo-step progression: cycles through 5 steps when backend
  // doesn't send step_label (covers everyday single-generation flow)
  const PSEUDO_STEPS = ['analyzing', 'identity_scan', 'crafting_prompt', 'generating_1_of_1', 'selecting']
  function startPseudoSteps() {
    pseudoStepTimers.current.forEach(clearTimeout)
    pseudoStepTimers.current = []
    const delays = [0, 4000, 10000, 16000, 50000]
    PSEUDO_STEPS.forEach((label, i) => {
      pseudoStepTimers.current.push(
        setTimeout(() => setStepLabel((cur) => cur ?? label), delays[i])
      )
    })
  }
  function clearPseudoSteps() {
    pseudoStepTimers.current.forEach(clearTimeout)
    pseudoStepTimers.current = []
  }

  useJobPoller(pollingJobId, (job) => {
    setCurrentJob(job)

    // Prefer backend step_label; pseudo steps serve as fallback
    if (job.step_label) setStepLabel(job.step_label)
    if (job.status === 'processing' || job.status === 'running') {
      setProgressStep((s) => Math.min(s + 1, 3))
    }

    if (isJobDone(job) || job.status === 'error' || job.status === 'failed') {
      clearPseudoSteps()
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

        // Referral nudge: show 8s after result, only for 2nd+ generation
        if ((freshUser?.gens_ok ?? 0) > 1 && !referralNudgeDismissed) {
          setTimeout(() => setShowReferralNudge(true), 8000)
        }

        // Fetch identity passport (once per session after first gen)
        if (!identityPassport) {
          getIdentityPassport().then((ip) => { if (ip.detected) setIdentityPassport(ip) }).catch(() => null)
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
    setShowReferralNudge(false)
    setProgressStep(0)
    setStepLabel(undefined)
    startPseudoSteps()

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
        style_variant: styleVariant || undefined,
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
    setShowReferralNudge(false)
    setProgressStep(0)
    setStepLabel(undefined)
    startPseudoSteps()
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
        toast.error('Not a direct image link — right-click the image → "Copy image address"')
      } else {
        toast.error('Could not load image')
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
            <motion.button
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => { tg?.HapticFeedback?.selectionChanged(); track('leaderboard_strip_tapped'); setShowLeaderboard(true) }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-[12px] bg-[#F5F5F7] text-left"
            >
              <span className="text-[13px] flex-shrink-0">🏆</span>
              <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-hidden">
                {leaderboard.entries.slice(0, 3).map((e, i) => (
                  <span
                    key={e.rank}
                    className={`text-[11px] font-medium truncate max-w-[72px] ${e.is_me ? 'text-[#6C47FF]' : 'text-[#1D1D1F]'}`}
                  >
                    {['🥇','🥈','🥉'][i]} {e.display_name}
                  </span>
                ))}
              </div>
              {leaderboard.my_rank ? (
                <span className="text-[11px] font-semibold text-[#6C47FF] flex-shrink-0">
                  #{leaderboard.my_rank} →
                </span>
              ) : (
                <span className="text-[11px] text-[#AEAEB2] flex-shrink-0">View →</span>
              )}
            </motion.button>
          )}
        </AnimatePresence>

        {/* Persistent quest notification pill — shown on mount when quest is claimable */}
        <AnimatePresence>
          {claimableQuest && !currentJob && questPillDismissedFor !== claimableQuest.id && (
            <motion.div
              initial={{ opacity: 0, y: -6, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 300, damping: 28 }}
              className="flex items-center gap-3 px-4 py-3 rounded-card bg-gradient-to-r from-[#6C47FF]/10 to-[#FF2D78]/10 border border-[#6C47FF]/20"
            >
              <span className="text-[20px]">⚡</span>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-[#1D1D1F]">Quest ready: {claimableQuest.title}</p>
                <p className="text-[11px] text-[#6E6E73]">+{claimableQuest.reward}⚡ waiting for you</p>
              </div>
              <button
                onClick={() => handleQuestClaim(claimableQuest.id)}
                disabled={claimingQuest}
                className="px-3 py-1.5 rounded-full bg-[#6C47FF] text-white text-[11px] font-bold disabled:opacity-60 shrink-0"
              >
                {claimingQuest ? '…' : `Claim +${claimableQuest.reward}⚡`}
              </button>
              <button
                onClick={() => setQuestPillDismissedFor(claimableQuest.id)}
                className="w-6 h-6 flex items-center justify-center text-[#AEAEB2] shrink-0 -mr-1"
              >
                ✕
              </button>
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

        {/* Identity passport chip — shown after first generation detects face attributes */}
        {identityPassport?.detected && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#6C47FF]/8 border border-[#6C47FF]/20 self-start"
          >
            <span className="text-[12px]">👤</span>
            <span className="text-[11px] font-semibold text-[#6C47FF]">
              {[identityPassport.gender, identityPassport.age_range, identityPassport.skin_tone && `${identityPassport.skin_tone} skin`]
                .filter(Boolean).join(' · ')}
            </span>
            <span className="text-[10px] text-[#6C47FF]/60">✨ Optimized</span>
          </motion.div>
        )}

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
                <p className="text-[13px] font-semibold text-[#1D1D1F]">📎 Style reference</p>
                <p className="text-[11px] text-[#6E6E73] mt-0.5">Upload a photo of the look you want to recreate</p>
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
                      placeholder="Paste a link (Pinterest, Instagram…)"
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
                    <span className="text-[11px] text-[#AEAEB2]">or</span>
                    <div className="flex-1 h-px bg-[#E5E5EA]" />
                  </div>

                  <label
                    htmlFor="ref-upload"
                    className="flex items-center justify-center gap-2 py-2.5 rounded-[10px] bg-white border border-[#E5E5EA] text-[13px] font-medium text-[#1D1D1F] cursor-pointer active:bg-[#F5F5F7]"
                  >
                    <Upload size={14} className="text-[#6C47FF]" />
                    Upload from phone
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

        {/* Streak at risk — handled by modal overlay, no inline banner */}

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

        {/* Monthly Viral Challenge Card */}
        <AnimatePresence>
          {monthlyChallenge?.active && !challengeDismissed && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full rounded-card overflow-hidden border border-[#6C47FF]/20"
              style={{ background: 'linear-gradient(135deg, #1A1A2E 0%, #2C1654 100%)' }}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 pt-3 pb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{monthlyChallenge.mode_emoji}</span>
                  <div>
                    <p className="text-[13px] font-bold text-white">{monthlyChallenge.name}</p>
                    <p className="text-[10px] text-white/60">{monthlyChallenge.days_left}d left · {monthlyChallenge.total_participants ?? 0} competing</p>
                  </div>
                </div>
                <button onClick={() => setChallengeDismissed(true)} className="text-white/40 text-lg leading-none">✕</button>
              </div>

              {/* Prizes row */}
              <div className="flex gap-2 px-4 pb-3">
                {[
                  { rank: '🥇', prize: monthlyChallenge.prize_top1 },
                  { rank: '🥈', prize: monthlyChallenge.prize_top2 },
                  { rank: '🥉', prize: monthlyChallenge.prize_top3 },
                ].map(({ rank, prize }) => (
                  <div key={rank} className="flex-1 text-center bg-white/10 rounded-[10px] py-1.5">
                    <p className="text-[16px] leading-none">{rank}</p>
                    <p className="text-[11px] font-bold text-[#FFD700]">+{prize}⚡</p>
                  </div>
                ))}
              </div>

              {/* Top 3 mini leaderboard */}
              {monthlyChallenge.top3 && monthlyChallenge.top3.length > 0 && (
                <div className="px-4 pb-3 space-y-1">
                  {monthlyChallenge.top3.map((e) => (
                    <div key={e.rank} className="flex items-center justify-between">
                      <span className="text-[11px] text-white/70">{e.rank}. {e.display_name}{e.is_me ? ' (you)' : ''}</span>
                      <span className="text-[11px] font-semibold text-white">{e.gens} gens</span>
                    </div>
                  ))}
                  {monthlyChallenge.my_rank && monthlyChallenge.my_rank > 3 && (
                    <div className="flex items-center justify-between pt-0.5 border-t border-white/10">
                      <span className="text-[11px] text-[#6C47FF] font-semibold">#{monthlyChallenge.my_rank} You</span>
                      <span className="text-[11px] font-semibold text-white">{monthlyChallenge.my_gens ?? 0} gens</span>
                    </div>
                  )}
                </div>
              )}

              {/* CTA */}
              <button
                onClick={() => {
                  tg?.HapticFeedback?.impactOccurred('medium')
                  if (monthlyChallenge.mode_key) {
                    useAppStore.getState().setPhotoshootMode(monthlyChallenge.mode_key)
                    track('monthly_challenge_cta_tapped', { mode: monthlyChallenge.mode_key })
                  }
                  setChallengeDismissed(true)
                }}
                className="w-full py-3 text-white text-[13px] font-bold"
                style={{ background: 'linear-gradient(90deg, #6C47FF, #FF2D78)' }}
              >
                Generate with {monthlyChallenge.mode_emoji} {monthlyChallenge.mode_label} →
              </button>
            </motion.div>
          )}
        </AnimatePresence>

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

        {/* Post-generation referral nudge — shows 8s after result, 2nd+ gen only */}
        {showReferralNudge && !batchJobs.length && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
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
                onClick={() => { setReferralNudgeDismissed(true); setShowReferralNudge(false) }}
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
        onSelect={(newMode, desc, variant) => {
          setPhotoshootMode(newMode)
          if (desc) setCustomDesc(desc)
          setStyleVariant(variant ?? '')
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

      {/* Leaderboard modal */}
      <AnimatePresence>
        {showLeaderboard && leaderboard && (
          <LeaderboardModal data={leaderboard} onClose={() => setShowLeaderboard(false)} />
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

      {/* Streak-at-risk modal */}
      <AnimatePresence>
        {showStreakModal && (() => {
          const lastGen = user?.last_gen_at ?? 0
          const hoursSince = (Date.now() / 1000 - lastGen) / 3600
          const hoursLeft = Math.max(0, Math.ceil(24 - hoursSince))
          const hasSelfie = !!selfieB64
          function dismiss() { setShowStreakModal(false) }
          function snooze() {
            localStorage.setItem('streak_risk_snoozed', String(Date.now()))
            setShowStreakModal(false)
            track('streak_modal_snoozed', { streak, hours_since: Math.round(hoursSince) })
          }
          function handleGenerate() {
            dismiss()
            track('streak_modal_generate', { streak })
            generate()
          }
          function handleUpload() {
            dismiss()
            track('streak_modal_upload', { streak })
            ;(document.getElementById('selfie-file-input') as HTMLInputElement | null)?.click()
          }
          return (
            <motion.div
              key="streak-modal"
              className="fixed inset-0 z-[80] flex flex-col justify-end"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Backdrop */}
              <motion.div
                className="absolute inset-0 bg-black/50"
                onClick={snooze}
              />
              {/* Sheet */}
              <motion.div
                initial={{ y: '100%' }}
                animate={{ y: 0 }}
                exit={{ y: '100%' }}
                transition={{ type: 'spring', stiffness: 340, damping: 38 }}
                className="relative bg-white rounded-t-[28px] px-5 pt-5 pb-8"
              >
                {/* Handle */}
                <div className="w-10 h-1 rounded-full bg-[#D1D1D6] mx-auto mb-5" />

                {/* Flame + streak count */}
                <div className="flex flex-col items-center gap-2 mb-4">
                  <motion.div
                    animate={{ scale: [1, 1.18, 1] }}
                    transition={{ repeat: Infinity, duration: 1.1, ease: 'easeInOut' }}
                    className="text-[52px] leading-none"
                  >
                    🔥
                  </motion.div>
                  <p className="text-[22px] font-bold text-[#1D1D1F] text-center">
                    {streak}-day streak at risk!
                  </p>
                  <p className="text-[14px] text-[#6E6E73] text-center">
                    {hoursLeft > 0
                      ? `Only ${hoursLeft}h left — generate now to keep it alive`
                      : 'Generate right now before your streak breaks!'}
                  </p>
                </div>

                {/* Streak dots */}
                <div className="flex justify-center gap-1.5 mb-6">
                  {Array.from({ length: Math.min(streak, 7) }, (_, i) => (
                    <motion.div
                      key={i}
                      initial={{ scale: 0.7 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: i * 0.04, type: 'spring', stiffness: 400 }}
                      className="w-7 h-7 rounded-lg bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center"
                    >
                      <span className="text-[13px]">🔥</span>
                    </motion.div>
                  ))}
                  {streak > 7 && (
                    <div className="w-7 h-7 rounded-lg bg-orange-100 flex items-center justify-center">
                      <span className="text-[10px] font-bold text-orange-500">+{streak - 7}</span>
                    </div>
                  )}
                </div>

                {/* CTAs */}
                <div className="space-y-2.5">
                  {hasSelfie ? (
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={handleGenerate}
                      className="w-full py-4 rounded-[16px] text-white text-[15px] font-bold"
                      style={{ background: 'linear-gradient(135deg, #FF6B35, #FF9500)' }}
                    >
                      Generate Now →
                    </motion.button>
                  ) : (
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={handleUpload}
                      className="w-full py-4 rounded-[16px] text-white text-[15px] font-bold flex items-center justify-center gap-2"
                      style={{ background: 'linear-gradient(135deg, #FF6B35, #FF9500)' }}
                    >
                      <Upload size={17} />
                      Upload Selfie to Generate
                    </motion.button>
                  )}
                  <button
                    onClick={snooze}
                    className="w-full py-3 text-[13px] text-[#6E6E73] font-medium"
                  >
                    Remind me later
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )
        })()}
      </AnimatePresence>
    </div>
  )
}
