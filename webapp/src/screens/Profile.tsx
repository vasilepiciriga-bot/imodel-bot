import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Flame, Users, Camera, CheckCircle2, Copy, Share2, Gift, Target, Trophy } from 'lucide-react'
import confetti from 'canvas-confetti'
import { useAppStore } from '../store/appStore'
import { claimDaily, getChallenge, getReferral, getMe } from '../api/session'
import { setPortfolioVisibility } from '../api/portfolio'
import { createGift } from '../api/gift'
import { createGiftSub } from '../api/shop'
import { getQuests, claimQuest, getAchievements, setLanguage } from '../api/quests'
import { getLeaderboard } from '../api/leaderboard'
import { AchievementPopup } from '../components/shared/AchievementPopup'
import { HomeScreenModal } from '../components/HomeScreenModal'
import { hap } from '../lib/haptics'
import { track } from '../api/analytics'
import type { ReferralData } from '../api/session'
import type { LeaderboardData } from '../api/leaderboard'
import type { QuestItem, Achievement } from '../types'

const tg = window.Telegram?.WebApp

const LANGS = ['🇷🇺', '🇺🇸', '🇩🇪', '🇸🇦']
const LANG_CODES = ['ru', 'en', 'de', 'ar']

function formatCountdown(secs: number): string {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function QuestCard({ quest, onClaim, onTap }: { quest: QuestItem; onClaim: (id: string) => void; onTap?: () => void }) {
  const pct = Math.min(1, quest.progress / quest.target)
  const Wrapper = onTap && !quest.claimed && !quest.claimable ? 'button' : 'div'
  return (
    <Wrapper
      className={`flex items-center gap-3 py-3 border-b border-black/[0.04] last:border-0 w-full text-left${onTap && !quest.claimed && !quest.claimable ? ' active:opacity-70' : ''}`}
      onClick={onTap && !quest.claimed && !quest.claimable ? onTap : undefined}
    >
      <span className="text-[22px] w-8 text-center flex-shrink-0">{quest.icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-semibold text-[#1D1D1F] truncate">{quest.title}</p>
        <div className="mt-1.5 flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-[#F5F5F7] overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78]"
              initial={{ width: 0 }}
              animate={{ width: `${pct * 100}%` }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            />
          </div>
          <span className="text-[10px] text-[#6E6E73] flex-shrink-0">{quest.progress}/{quest.target}</span>
        </div>
      </div>
      {quest.claimable ? (
        <motion.button
          whileTap={{ scale: 0.94 }}
          onClick={(e) => { e.stopPropagation(); hap.success(); onClaim(quest.id) }}
          className="flex-shrink-0 px-3 py-1.5 rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[11px] font-bold"
        >
          +{quest.reward}⚡
        </motion.button>
      ) : quest.claimed ? (
        <span className="flex-shrink-0 text-[11px] font-semibold text-[#34C759]">✓ Done</span>
      ) : onTap ? (
        <span className="flex-shrink-0 text-[11px] font-semibold text-[#6C47FF]">Tap →</span>
      ) : (
        <span className="flex-shrink-0 text-[11px] font-medium text-[#6E6E73]">+{quest.reward}⚡</span>
      )}
    </Wrapper>
  )
}

export default function Profile() {
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const [dailyClaimed, setDailyClaimed] = useState(false)
  const [nextBonusIn, setNextBonusIn] = useState<number | null>(null)
  const [claimLoading, setClaimLoading] = useState(false)
  const [referral, setReferral] = useState<ReferralData | null>(null)
  const [copied, setCopied] = useState(false)
  const [giftAmount, setGiftAmount] = useState<number | null>(null)
  const [giftLoading, setGiftLoading] = useState(false)
  const [giftSent, setGiftSent] = useState(false)
  const [quests, setQuests] = useState<QuestItem[]>([])
  const [achievements, setAchievements] = useState<Achievement[]>([])
  const [newAchievement, setNewAchievement] = useState<Achievement | null>(null)
  const [homeScreenOpen, setHomeScreenOpen] = useState(false)
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null)
  const setTab = useAppStore((s) => s.setTab)
  const setActivePreset = useAppStore((s) => s.setActivePreset)
  const challenge = useAppStore((s) => s.challenge)
  const challengeLoaded = useAppStore((s) => s.challengeLoaded)

  useEffect(() => {
    if (!challengeLoaded) {
      useAppStore.getState().setChallengeLoaded(true)
      getChallenge()
        .then((c) => useAppStore.getState().setChallenge(c))
        .catch(() => null)
    }
    getReferral().then(setReferral).catch(() => null)
    getLeaderboard().then(setLeaderboard).catch(() => null)
    getQuests().then(({ quests: q, claimable }) => {
      setQuests(q)
      useAppStore.getState().setProfileBadge(claimable)
    }).catch(() => null)
    getAchievements().then(({ achievements: a, newly_unlocked }) => {
      setAchievements(a)
      if (newly_unlocked.length > 0) {
        const found = a.find((x) => x.id === newly_unlocked[0])
        if (found) setNewAchievement(found)
      }
    }).catch(() => null)
  }, [])

  useEffect(() => {
    if (!nextBonusIn) return
    const t = setInterval(() => setNextBonusIn((n) => (n! > 0 ? n! - 60 : null)), 60_000)
    return () => clearInterval(t)
  }, [nextBonusIn])

  async function handleDailyBonus() {
    setClaimLoading(true)
    try {
      const result = await claimDaily()
      setDailyClaimed(true)
      confetti({ particleCount: 80, spread: 60, origin: { y: 0.5 }, colors: ['#6C47FF', '#FF2D78', '#FFD700'] })
      hap.success()
      if (user) setUser({ ...user, credits: result.credits, streak: result.streak })
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'data' in e) {
        const data = (e as { data?: { next_at?: number } }).data
        if (data?.next_at) setNextBonusIn(Math.round((data.next_at * 1000 - Date.now()) / 1000))
      }
    } finally {
      setClaimLoading(false)
    }
  }

  async function handleClaimQuest(questId: string) {
    try {
      const res = await claimQuest(questId)
      setQuests((prev) => {
        const updated = prev.map((q) => q.id === questId ? { ...q, claimed: true, claimable: false } : q)
        useAppStore.getState().setProfileBadge(updated.filter((q) => q.claimable).length)
        return updated
      })
      if (user) setUser({ ...user, credits: res.new_balance })
      confetti({ particleCount: 60, spread: 55, origin: { y: 0.6 }, colors: ['#6C47FF', '#FFD700'] })
    } catch { /* noop */ }
  }

  async function handleLanguage(code: string) {
    hap.select()
    try {
      await setLanguage(code)
      if (user) setUser({ ...user, language: code })
    } catch { /* noop */ }
  }

  function handleCopyLink() {
    if (!referral) return
    navigator.clipboard.writeText(referral.link).catch(() => null)
    setCopied(true)
    hap.success()
    setTimeout(() => setCopied(false), 2000)
  }

  function handleShareLink() {
    if (!referral) return
    hap.light()
    const text = encodeURIComponent('Try AI photoshoots — turns your selfie into stunning photos!')
    const url = encodeURIComponent(referral.link)
    tg?.openLink(`https://t.me/share/url?url=${url}&text=${text}`)
  }

  async function handleGiftSub() {
    hap.medium()
    track('gift_sub_tapped')
    try {
      const { share_link, gift_days } = await createGiftSub()
      track('gift_sub_shared', { gift_days })
      const text = encodeURIComponent(`🎁 I'm gifting you ${gift_days} days of iModel Pro — AI portraits for free!`)
      tg?.openLink(`https://t.me/share/url?url=${encodeURIComponent(share_link)}&text=${text}`)
    } catch { /* noop */ }
  }

  async function handleSendGift(credits: number) {
    if (!user || user.credits < credits) return
    setGiftLoading(true)
    hap.medium()
    try {
      const { link } = await createGift(credits)
      setGiftSent(true)
      setGiftAmount(null)
      const updated = await getMe()
      setUser(updated)
      const text = encodeURIComponent("🎁 I'm gifting you AI photo credits!")
      tg?.openLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}`)
    } catch { /* noop */ } finally {
      setGiftLoading(false)
    }
  }

  const streak = user?.streak ?? 0
  const totalGens = user?.total_generated ?? 0
  const initials = (tg?.initDataUnsafe?.user?.first_name ?? 'U').charAt(0).toUpperCase()
  const username = tg?.initDataUnsafe?.user?.username
  const displayName = tg?.initDataUnsafe?.user?.first_name ?? 'User'
  const weekDays = Array.from({ length: 7 }, (_, i) => i < (streak % 7 || (streak > 0 ? 7 : 0)))

  // Member since
  const memberSinceDays = user?.first_seen
    ? Math.max(1, Math.floor((Date.now() / 1000 - user.first_seen) / 86400))
    : null

  const myRank = leaderboard?.my_rank ?? null
  const myWeeklyGens = leaderboard?.my_gens ?? 0
  const claimableCount = quests.filter((q) => q.claimable).length

  // Next milestone logic
  const GEN_MILESTONES = [10, 50, 100, 250, 500, 1000]
  const STREAK_MILESTONES = [3, 7, 14, 30, 60, 100]
  const nextGenMilestone = GEN_MILESTONES.find((m) => m > totalGens) ?? null
  const nextStreakMilestone = STREAK_MILESTONES.find((m) => m > streak) ?? null
  const milestoneDiff = (nextGenMilestone ? nextGenMilestone - totalGens : Infinity)
  const streakDiff = (nextStreakMilestone ? nextStreakMilestone - streak : Infinity)
  const showMilestone = milestoneDiff <= 15 || streakDiff <= 3
  const milestoneIsGen = milestoneDiff <= streakDiff
  const milestoneTarget = milestoneIsGen ? nextGenMilestone : nextStreakMilestone
  const milestoneProgress = milestoneIsGen ? totalGens : streak
  const milestoneRemaining = milestoneIsGen ? milestoneDiff : streakDiff
  const milestoneLabel = milestoneIsGen
    ? `${milestoneRemaining} more gen${milestoneRemaining !== 1 ? 's' : ''} → ${nextGenMilestone} total achievement`
    : `${milestoneRemaining} more day${milestoneRemaining !== 1 ? 's' : ''} → ${nextStreakMilestone}-day streak badge`

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Achievement popup */}
      <AnimatePresence>
        {newAchievement && (
          <AchievementPopup
            achievement={newAchievement}
            onDone={() => setNewAchievement(null)}
          />
        )}
      </AnimatePresence>

      <div className="px-4 pt-4 pb-2">
        <h1 className="text-[22px] font-bold text-[#1D1D1F]">👤 Profile</h1>
      </div>

      <div className="flex-1 px-4 pb-6 space-y-4">
        {/* Avatar + name */}
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] flex items-center justify-center text-2xl font-bold text-white">
            {initials}
          </div>
          <div>
            <p className="text-[18px] font-bold text-[#1D1D1F]">{displayName}</p>
            {username && <p className="text-[13px] text-[#6E6E73]">@{username}</p>}
            {memberSinceDays !== null && (
              <p className="text-[11px] text-[#AEAEB2] mt-0.5">
                Member since {memberSinceDays < 7
                  ? `${memberSinceDays}d`
                  : memberSinceDays < 30
                    ? `${Math.floor(memberSinceDays / 7)}w`
                    : `${Math.floor(memberSinceDays / 30)}mo`} ago
              </p>
            )}
            {user?.plan && user.plan !== 'free' && (
              <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[10px] font-bold">
                ✦ {user.plan.toUpperCase()}
              </span>
            )}
          </div>
        </div>

        {/* Stats row — 4 cards */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { icon: Camera,  value: totalGens,                   label: 'Photos',  color: 'text-[#6C47FF]', fill: false },
            { icon: Flame,   value: streak,                      label: 'Streak',  color: 'text-orange-500', fill: true },
            { icon: Users,   value: user?.friends_invited ?? 0,  label: 'Invited', color: 'text-[#34C759]',  fill: false },
            { icon: Target,  value: achievements.filter((a) => a.unlocked).length, label: 'Awards', color: 'text-[#FF9500]', fill: false },
          ].map(({ icon: Icon, value, label, color, fill }) => (
            <div key={label} className="flex flex-col items-center p-2.5 bg-white rounded-[16px] shadow-sm">
              <Icon size={16} className={`${color} mb-1`} fill={fill ? 'currentColor' : 'none'} />
              <span className="text-[18px] font-bold text-[#1D1D1F] leading-none">{value}</span>
              <span className="text-[9px] text-[#6E6E73] mt-0.5 text-center leading-tight">{label}</span>
            </div>
          ))}
        </div>

        {/* Weekly leaderboard rank card */}
        {myRank !== null && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3 px-4 py-3 bg-white rounded-[16px] shadow-sm"
          >
            <div className="w-9 h-9 rounded-[10px] bg-gradient-to-br from-[#FFD700]/20 to-[#FF9500]/20 flex items-center justify-center flex-shrink-0">
              <Trophy size={18} className="text-[#FF9500]" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-semibold text-[#1D1D1F]">
                Weekly rank: <span className="text-[#FF9500]">#{myRank}</span>
              </p>
              <p className="text-[11px] text-[#6E6E73]">{myWeeklyGens} gen{myWeeklyGens !== 1 ? 's' : ''} this week</p>
            </div>
            <button
              onClick={() => useAppStore.getState().setTab('gallery')}
              className="text-[11px] font-semibold text-[#6C47FF]"
            >
              Leaderboard →
            </button>
          </motion.div>
        )}

        {/* Next milestone card */}
        {showMilestone && milestoneTarget && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 rounded-[20px] bg-gradient-to-r from-[#6C47FF]/10 to-[#FF2D78]/10 border border-[#6C47FF]/20"
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[18px]">🎯</span>
              <p className="text-[13px] font-bold text-[#1D1D1F]">Almost there!</p>
            </div>
            <p className="text-[12px] text-[#6E6E73] mb-2.5">{milestoneLabel}</p>
            <div className="h-2 rounded-full bg-black/[0.06] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78]"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(100, (milestoneProgress / milestoneTarget) * 100)}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
              />
            </div>
            <p className="text-[10px] text-[#6E6E73] mt-1.5 text-right">{milestoneProgress}/{milestoneTarget}</p>
          </motion.div>
        )}

        {/* Streak calendar */}
        {streak > 0 && (
          <div className="p-4 rounded-card bg-white shadow-sm">
            <p className="text-[13px] font-semibold text-[#1D1D1F] mb-3">🔥 {streak} day streak</p>
            <div className="flex gap-1.5">
              {weekDays.map((active, i) => (
                <motion.div
                  key={i}
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className={`flex-1 aspect-square rounded-lg ${active ? 'bg-gradient-to-br from-[#6C47FF] to-[#FF2D78]' : 'bg-[#F5F5F7]'}`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Daily Bonus */}
        <div className="rounded-card overflow-hidden">
          <AnimatePresence mode="wait">
            {dailyClaimed ? (
              <motion.div key="claimed" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3 p-4 bg-[#34C759]/10 border border-[#34C759]/20">
                <CheckCircle2 size={24} className="text-[#34C759]" />
                <div>
                  <p className="text-[14px] font-semibold text-[#1D1D1F]">Daily bonus claimed!</p>
                  <p className="text-[12px] text-[#6E6E73]">Come back tomorrow</p>
                </div>
              </motion.div>
            ) : nextBonusIn ? (
              <motion.div key="waiting" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="flex items-center justify-between p-4 bg-[#F5F5F7] rounded-card">
                <div>
                  <p className="text-[14px] font-semibold text-[#1D1D1F]">Daily Bonus</p>
                  <p className="text-[12px] text-[#6E6E73]">Next in {formatCountdown(nextBonusIn)}</p>
                </div>
                <span className="text-2xl">⏳</span>
              </motion.div>
            ) : (
              <motion.button key="available" whileTap={{ scale: 0.98 }} onClick={handleDailyBonus}
                disabled={claimLoading}
                className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-[#34C759]/20 to-[#34C759]/10 border border-[#34C759]/30 rounded-card">
                <div className="text-left">
                  <p className="text-[15px] font-semibold text-[#1D1D1F]">🎁 Daily Bonus</p>
                  <p className="text-[12px] text-[#6E6E73]">+1 free generation · streak bonus</p>
                </div>
                <span className="text-[22px]">→</span>
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* Quick Quests */}
        {quests.length > 0 && (
          <div className="rounded-card bg-white shadow-sm overflow-hidden">
            <div className="px-4 pt-4 pb-2 flex items-center justify-between">
              <p className="text-[15px] font-bold text-[#1D1D1F]">⚡ Daily Quests</p>
              {claimableCount > 0 && (
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="w-5 h-5 rounded-full bg-[#FF2D78] text-white text-[10px] font-bold flex items-center justify-center"
                >
                  {claimableCount}
                </motion.span>
              )}
            </div>
            <div className="px-4 pb-2">
              {quests.filter((q) => q.type === 'daily').map((q) => (
                <QuestCard key={q.id} quest={q} onClaim={handleClaimQuest} />
              ))}
            </div>
            {quests.some((q) => q.type !== 'daily') && (
              <>
                <div className="px-4 pt-2 pb-1">
                  <p className="text-[11px] font-semibold text-[#6E6E73] uppercase tracking-wide">Milestones</p>
                </div>
                <div className="px-4 pb-2">
                  {quests.filter((q) => q.type !== 'daily').map((q) => (
                    <QuestCard
                      key={q.id}
                      quest={q}
                      onClaim={handleClaimQuest}
                      onTap={q.id === 'add_to_home_screen' && !q.claimed ? () => { hap.medium(); setHomeScreenOpen(true) } : undefined}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Daily Challenge */}
        {challenge && (
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={() => {
              hap.medium()
              setActivePreset({ key: challenge.preset_key, label: challenge.label, category: 'challenge', is_premium: false, emoji: '⚡' })
              setTab('studio')
            }}
            className="w-full flex items-center gap-3 p-4 rounded-card bg-gradient-to-r from-[#FF9500]/10 to-[#FF2D78]/10 border border-[#FF9500]/20"
          >
            <span className="text-2xl">⚡</span>
            <div className="flex-1 text-left">
              <p className="text-[14px] font-semibold text-[#1D1D1F]">Daily Challenge</p>
              <p className="text-[12px] text-[#6E6E73]">Today: {challenge.label} · +{challenge.bonus_credits} bonus credits</p>
            </div>
            <span className="text-[13px] font-medium text-[#FF9500]">Try →</span>
          </motion.button>
        )}

        {/* Achievements row */}
        {achievements.length > 0 && (
          <div className="rounded-card bg-white shadow-sm overflow-hidden">
            <div className="px-4 pt-4 pb-3">
              <p className="text-[15px] font-bold text-[#1D1D1F] mb-3">🏆 Achievements</p>
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                {achievements.map((a) => (
                  <div
                    key={a.id}
                    title={a.desc}
                    className={`flex-shrink-0 w-12 h-12 rounded-[14px] flex items-center justify-center text-[22px] relative ${
                      a.unlocked
                        ? 'bg-gradient-to-br from-[#6C47FF]/20 to-[#FF2D78]/20 border border-[#6C47FF]/30'
                        : 'bg-[#F5F5F7] grayscale opacity-40'
                    }`}
                  >
                    {a.icon}
                    {a.unlocked && (
                      <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-[#6C47FF] border-2 border-white" />
                    )}
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-[#6E6E73] mt-2">
                {achievements.filter((a) => a.unlocked).length}/{achievements.length} unlocked
              </p>
            </div>
          </div>
        )}

        {/* Subscription status */}
        {user?.plan && user.plan !== 'free' && (
          <div className="p-4 rounded-card bg-gradient-to-r from-[#6C47FF]/10 to-[#FF2D78]/10 border border-[#6C47FF]/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-semibold text-[#1D1D1F]">✦ {user.plan.toUpperCase()} Plan</p>
                {user.plan_expiry && (
                  <p className="text-[12px] text-[#6E6E73] mt-0.5">Renews {new Date(user.plan_expiry).toLocaleDateString()}</p>
                )}
              </div>
              <CheckCircle2 size={20} className="text-[#6C47FF]" />
            </div>
          </div>
        )}

        {/* Gift Credits */}
        <AnimatePresence mode="wait">
          {giftSent ? (
            <motion.div key="giftsent" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="flex items-center gap-3 p-4 rounded-card bg-[#FF2D78]/10 border border-[#FF2D78]/20">
              <Gift size={22} className="text-[#FF2D78]" />
              <div>
                <p className="text-[14px] font-semibold text-[#1D1D1F]">Gift sent! 🎉</p>
                <p className="text-[12px] text-[#6E6E73]">Share the link so your friend can claim it</p>
              </div>
            </motion.div>
          ) : giftAmount ? (
            <motion.div key="giftpick" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="p-4 rounded-card bg-white shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[14px] font-semibold text-[#1D1D1F]">🎁 Send {giftAmount}⚡ as gift</p>
                <button onClick={() => setGiftAmount(null)} className="text-[12px] text-[#6E6E73]">Cancel</button>
              </div>
              <p className="text-[12px] text-[#6E6E73] mb-3">
                Your balance: {user?.credits ?? 0}⚡ → {(user?.credits ?? 0) - giftAmount}⚡ after gift
              </p>
              <motion.button whileTap={{ scale: 0.97 }} onClick={() => handleSendGift(giftAmount)}
                disabled={giftLoading || (user?.credits ?? 0) < giftAmount}
                className="w-full py-3 rounded-[12px] bg-gradient-to-r from-[#FF2D78] to-[#6C47FF] text-white text-[14px] font-bold disabled:opacity-40">
                {giftLoading ? 'Creating link…' : 'Create & Share Gift →'}
              </motion.button>
            </motion.div>
          ) : (
            <motion.div key="giftcard" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="p-4 rounded-card bg-white shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <Gift size={16} className="text-[#FF2D78]" />
                <p className="text-[14px] font-semibold text-[#1D1D1F]">Gift Credits to a Friend</p>
              </div>
              <p className="text-[12px] text-[#6E6E73] mb-3">They get credits instantly · you get +1⚡ when they claim</p>
              <div className="flex gap-2">
                {[5, 10, 25].map((amt) => (
                  <motion.button key={amt} whileTap={{ scale: 0.93 }}
                    onClick={() => { hap.light(); setGiftAmount(amt) }}
                    disabled={(user?.credits ?? 0) < amt}
                    className="flex-1 py-2.5 rounded-[10px] bg-[#FF2D78]/10 border border-[#FF2D78]/20 text-[#FF2D78] text-[13px] font-bold disabled:opacity-30">
                    {amt}⚡
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Referral card */}
        {referral && (
          <div className="rounded-card bg-white shadow-sm overflow-hidden">
            {/* Header with dual-avatar visual */}
            <div className="px-4 pt-4 pb-3 bg-gradient-to-r from-[#6C47FF]/8 to-[#FF2D78]/8">
              <div className="flex items-center gap-3 mb-2">
                {/* Dual overlapping avatars */}
                <div className="relative w-[52px] h-8 shrink-0">
                  <div className="absolute left-0 w-8 h-8 rounded-full bg-gradient-to-br from-[#6C47FF] to-[#9B6DFF] border-2 border-white flex items-center justify-center text-white text-[14px] font-bold z-10">
                    {(user?.first_name?.[0] ?? 'Y').toUpperCase()}
                  </div>
                  <div className="absolute left-5 w-8 h-8 rounded-full bg-gradient-to-br from-[#FF2D78] to-[#FF6B9D] border-2 border-white flex items-center justify-center text-white text-[14px]">
                    👤
                  </div>
                </div>
                <div className="flex-1">
                  <p className="text-[15px] font-bold text-[#1D1D1F] leading-tight">You + Friend each earn</p>
                  <p className="text-[12px] text-[#6C47FF] font-semibold">
                    +{referral.bonus_per_invite}⚡ you · +{referral.bonus_for_new}⚡ them
                  </p>
                </div>
              </div>
              <p className="text-[11px] text-[#6E6E73]">{referral.invited_count} friend{referral.invited_count !== 1 ? 's' : ''} invited · {referral.credits_earned}⚡ earned</p>
            </div>

            {/* Progress to next milestone */}
            {referral.next_milestone != null && (
              <div className="px-4 py-3 border-b border-black/[0.04]">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[11px] font-medium text-[#1D1D1F]">
                    {referral.next_milestone - referral.invited_count} more friend{referral.next_milestone - referral.invited_count !== 1 ? 's' : ''} → +{referral.next_milestone_bonus}⚡ bonus
                  </p>
                  <span className="text-[10px] text-[#6E6E73]">{referral.invited_count}/{referral.next_milestone}</span>
                </div>
                <div className="w-full h-1.5 bg-[#F5F5F7] rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, (referral.invited_count / referral.next_milestone) * 100)}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut', delay: 0.3 }}
                    className="h-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] rounded-full"
                  />
                </div>
                {referral.milestones.length > 0 && (
                  <div className="flex gap-1 mt-1.5">
                    {referral.milestones.map((ms) => (
                      <div key={ms.count} className="flex items-center gap-0.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${ms.reached ? 'bg-[#6C47FF]' : 'bg-[#D1D1D6]'}`} />
                        <span className={`text-[9px] ${ms.reached ? 'text-[#6C47FF] font-semibold' : 'text-[#6E6E73]'}`}>
                          {ms.count}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Link + actions */}
            <div className="px-4 py-3">
              <div className="flex items-center gap-2 px-3 py-2 bg-[#F5F5F7] rounded-[10px] mb-2">
                <span className="flex-1 text-[11px] text-[#6E6E73] truncate">{referral.link}</span>
              </div>
              <div className="flex gap-2 mb-2">
                <motion.button whileTap={{ scale: 0.96 }} onClick={handleCopyLink}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[10px] bg-[#6C47FF]/10 text-[#6C47FF] text-[12px] font-semibold">
                  <Copy size={13} />
                  {copied ? 'Copied!' : 'Copy link'}
                </motion.button>
                <motion.button whileTap={{ scale: 0.96 }} onClick={handleShareLink}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[10px] bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[12px] font-semibold">
                  <Share2 size={13} />
                  Share
                </motion.button>
              </div>
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={handleGiftSub}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-[10px] bg-gradient-to-r from-[#FF9500]/15 to-[#FF2D78]/10 border border-[#FF9500]/25 text-[#FF9500] text-[12px] font-semibold"
              >
                <Gift size={13} />
                🎁 Gift your friend 7 days of Pro →
              </motion.button>
            </div>
          </div>
        )}

        {/* Language selector */}
        <div>
          <p className="text-[12px] text-[#6E6E73] font-medium mb-2">Language</p>
          <div className="flex gap-2">
            {LANGS.map((flag, i) => (
              <motion.button
                key={LANG_CODES[i]}
                whileTap={{ scale: 0.88 }}
                onClick={() => handleLanguage(LANG_CODES[i])}
                className={`w-10 h-10 rounded-xl text-xl transition-all ${
                  user?.language === LANG_CODES[i]
                    ? 'ring-2 ring-[#6C47FF] bg-[#6C47FF]/10'
                    : 'bg-[#F5F5F7]'
                }`}
              >
                {flag}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Portfolio visibility */}
        <div className="p-4 rounded-card bg-[#F5F5F7]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[14px] font-semibold text-[#1D1D1F]">🔗 Public Portfolio</p>
              <p className="text-[11px] text-[#6E6E73] mt-0.5">Share your AI photos with a link</p>
            </div>
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={async () => {
                const next = !user?.portfolio_public
                try {
                  await setPortfolioVisibility(next)
                  const updated = await getMe()
                  setUser(updated)
                } catch { /* noop */ }
              }}
              className={`w-12 h-6 rounded-full transition-colors ${user?.portfolio_public ? 'bg-[#34C759]' : 'bg-[#D1D1D6]'}`}
            >
              <motion.div
                animate={{ x: user?.portfolio_public ? 24 : 2 }}
                transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                className="w-5 h-5 rounded-full bg-white shadow-sm"
              />
            </motion.button>
          </div>
          {user?.portfolio_public && user?.portfolio_url && (
            <motion.button
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              onClick={() => {
                const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(user.portfolio_url!)}&text=${encodeURIComponent('My AI portfolio ✨')}`
                tg?.openLink(shareUrl)
              }}
              className="mt-3 w-full py-2 rounded-[10px] bg-[#6C47FF]/10 text-[#6C47FF] text-[12px] font-semibold"
            >
              Share portfolio →
            </motion.button>
          )}
        </div>

        {/* Links */}
        <div className="flex gap-3 text-[12px] text-[#6E6E73]">
          <button onClick={() => tg?.openLink(user?.bot_link ?? 'https://t.me/imodelapp_bot')}>Privacy</button>
          <span>·</span>
          <button onClick={() => tg?.openLink(user?.bot_link ?? 'https://t.me/imodelapp_bot')}>Terms</button>
        </div>
      </div>

      {/* Home Screen quest modal */}
      <AnimatePresence>
        {homeScreenOpen && (
          <HomeScreenModal
            onClose={() => setHomeScreenOpen(false)}
            onCompleted={() => {
              setHomeScreenOpen(false)
              getQuests().then(({ quests: q, claimable }) => {
                setQuests(q)
                useAppStore.getState().setProfileBadge(claimable)
              }).catch(() => null)
              if (user) getMe().then((u) => setUser(u)).catch(() => null)
              confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 }, colors: ['#6C47FF', '#FF2D78', '#FFD700'] })
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
