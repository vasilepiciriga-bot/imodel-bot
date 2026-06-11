import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Flame, Users, Camera, CheckCircle2, Copy, Share2 } from 'lucide-react'
import confetti from 'canvas-confetti'
import { useAppStore } from '../store/appStore'
import { claimDaily, getChallenge, getReferral, getMe } from '../api/session'
import { setPortfolioVisibility } from '../api/portfolio'
import type { Challenge } from '../types'
import type { ReferralData } from '../api/session'

const tg = window.Telegram?.WebApp

const LANGS = ['🇷🇺', '🇺🇸', '🇩🇪', '🇸🇦']
const LANG_CODES = ['ru', 'en', 'de', 'ar']

function formatCountdown(secs: number): string {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function Profile() {
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [dailyClaimed, setDailyClaimed] = useState(false)
  const [nextBonusIn, setNextBonusIn] = useState<number | null>(null)
  const [claimLoading, setClaimLoading] = useState(false)
  const [referral, setReferral] = useState<ReferralData | null>(null)
  const [copied, setCopied] = useState(false)
  const setTab = useAppStore((s) => s.setTab)
  const setActivePreset = useAppStore((s) => s.setActivePreset)

  useEffect(() => {
    getChallenge().then(setChallenge).catch(() => null)
    getReferral().then(setReferral).catch(() => null)
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
      tg?.HapticFeedback?.notificationOccurred('success')
      if (user) {
        setUser({ ...user, credits: result.credits, streak: result.streak })
      }
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'data' in e) {
        const data = (e as { data?: { next_at?: number } }).data
        if (data?.next_at) {
          setNextBonusIn(Math.round((data.next_at * 1000 - Date.now()) / 1000))
        }
      }
    } finally {
      setClaimLoading(false)
    }
  }

  function handleCopyLink() {
    if (!referral) return
    navigator.clipboard.writeText(referral.link).catch(() => null)
    setCopied(true)
    tg?.HapticFeedback?.notificationOccurred('success')
    setTimeout(() => setCopied(false), 2000)
  }

  function handleShareLink() {
    if (!referral) return
    tg?.HapticFeedback?.impactOccurred('light')
    const text = encodeURIComponent('Try AI photoshoots — turns your selfie into stunning photos!')
    const url = encodeURIComponent(referral.link)
    tg?.openLink(`https://t.me/share/url?url=${url}&text=${text}`)
  }

  const streak = user?.streak ?? 0
  const initials = (user as { first_name?: string } | null)
    ? (tg?.initDataUnsafe?.user?.first_name ?? 'U').charAt(0).toUpperCase()
    : 'U'
  const username = tg?.initDataUnsafe?.user?.username
  const displayName = tg?.initDataUnsafe?.user?.first_name ?? 'User'

  const weekDays = Array.from({ length: 7 }, (_, i) => i < streak % 7)

  return (
    <div className="flex flex-col h-full overflow-y-auto">
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
            {user?.plan && user.plan !== 'free' && (
              <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[10px] font-bold">
                ✦ {user.plan.toUpperCase()}
              </span>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { icon: Camera, value: user?.total_generated ?? 0, label: 'Photos' },
            { icon: Flame, value: streak, label: 'Day streak', fill: true },
            { icon: Users, value: user?.friends_invited ?? 0, label: 'Friends' },
          ].map(({ icon: Icon, value, label, fill }) => (
            <div key={label} className="flex flex-col items-center p-3 bg-white rounded-card shadow-sm">
              <Icon size={18} className={fill ? 'text-orange-500 mb-1' : 'text-[#6C47FF] mb-1'} fill={fill ? 'currentColor' : 'none'} />
              <span className="text-[22px] font-bold text-[#1D1D1F] leading-none">{value}</span>
              <span className="text-[10px] text-[#6E6E73] mt-0.5">{label}</span>
            </div>
          ))}
        </div>

        {/* Streak calendar */}
        {streak > 0 && (
          <div className="p-4 rounded-card bg-white shadow-sm">
            <p className="text-[13px] font-semibold text-[#1D1D1F] mb-3">
              🔥 {streak} day streak
            </p>
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

        {/* Daily Bonus Button */}
        <div className="rounded-card overflow-hidden">
          <AnimatePresence mode="wait">
            {dailyClaimed ? (
              <motion.div
                key="claimed"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3 p-4 bg-[#34C759]/10 border border-[#34C759]/20"
              >
                <CheckCircle2 size={24} className="text-[#34C759]" />
                <div>
                  <p className="text-[14px] font-semibold text-[#1D1D1F]">Daily bonus claimed!</p>
                  <p className="text-[12px] text-[#6E6E73]">Come back tomorrow</p>
                </div>
              </motion.div>
            ) : nextBonusIn ? (
              <motion.div
                key="waiting"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center justify-between p-4 bg-[#F5F5F7] rounded-card"
              >
                <div>
                  <p className="text-[14px] font-semibold text-[#1D1D1F]">Daily Bonus</p>
                  <p className="text-[12px] text-[#6E6E73]">Next in {formatCountdown(nextBonusIn)}</p>
                </div>
                <span className="text-2xl">⏳</span>
              </motion.div>
            ) : (
              <motion.button
                key="available"
                whileTap={{ scale: 0.98 }}
                onClick={handleDailyBonus}
                disabled={claimLoading}
                className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-[#34C759]/20 to-[#34C759]/10 border border-[#34C759]/30 rounded-card"
              >
                <div className="text-left">
                  <p className="text-[15px] font-semibold text-[#1D1D1F]">🎁 Daily Bonus</p>
                  <p className="text-[12px] text-[#6E6E73]">+1 free generation · streak bonus</p>
                </div>
                <span className="text-[22px]">→</span>
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* Daily Challenge */}
        {challenge && (
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={() => {
              tg?.HapticFeedback?.impactOccurred('medium')
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

        {/* Subscription status */}
        {user?.plan && user.plan !== 'free' && (
          <div className="p-4 rounded-card bg-gradient-to-r from-[#6C47FF]/10 to-[#FF2D78]/10 border border-[#6C47FF]/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[14px] font-semibold text-[#1D1D1F]">✦ {user.plan.toUpperCase()} Plan</p>
                {user.plan_expiry && (
                  <p className="text-[12px] text-[#6E6E73] mt-0.5">
                    Renews {new Date(user.plan_expiry).toLocaleDateString()}
                  </p>
                )}
              </div>
              <CheckCircle2 size={20} className="text-[#6C47FF]" />
            </div>
          </div>
        )}

        {/* Referral card */}
        {referral && (
          <div className="rounded-card bg-white shadow-sm overflow-hidden">
            <div className="px-4 pt-4 pb-3 bg-gradient-to-r from-[#6C47FF]/8 to-[#FF2D78]/8">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[15px] font-bold text-[#1D1D1F]">👥 Invite Friends</p>
                <span className="text-[12px] font-semibold text-[#6C47FF]">
                  +{referral.bonus_per_invite}⚡ you · +{referral.bonus_for_new}⚡ them
                </span>
              </div>
              <p className="text-[12px] text-[#6E6E73]">
                {referral.invited_count} invited · {referral.credits_earned} credits earned
              </p>
            </div>

            {/* Milestone progress */}
            {referral.milestones.length > 0 && (
              <div className="px-4 py-3 border-b border-black/[0.04]">
                <div className="flex gap-2">
                  {referral.milestones.map((ms) => (
                    <div key={ms.count} className="flex-1 flex flex-col items-center gap-1">
                      <div className={`w-full h-1.5 rounded-full ${ms.reached ? 'bg-[#6C47FF]' : 'bg-[#F5F5F7]'}`} />
                      <span className={`text-[9px] font-medium ${ms.reached ? 'text-[#6C47FF]' : 'text-[#6E6E73]'}`}>
                        {ms.count} · +{ms.bonus}⚡
                      </span>
                    </div>
                  ))}
                </div>
                {referral.next_milestone && (
                  <p className="text-[11px] text-[#6E6E73] mt-1.5">
                    {referral.next_milestone - referral.invited_count} more to unlock +{referral.next_milestone_bonus}⚡ bonus
                  </p>
                )}
              </div>
            )}

            {/* Link + buttons */}
            <div className="px-4 py-3">
              <div className="flex items-center gap-2 px-3 py-2 bg-[#F5F5F7] rounded-[10px] mb-2">
                <span className="flex-1 text-[11px] text-[#6E6E73] truncate">{referral.link}</span>
              </div>
              <div className="flex gap-2">
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={handleCopyLink}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[10px] bg-[#6C47FF]/10 text-[#6C47FF] text-[12px] font-semibold"
                >
                  <Copy size={13} />
                  {copied ? 'Copied!' : 'Copy link'}
                </motion.button>
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={handleShareLink}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[10px] bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[12px] font-semibold"
                >
                  <Share2 size={13} />
                  Share
                </motion.button>
              </div>
            </div>
          </div>
        )}

        {/* Language selector */}
        <div>
          <p className="text-[12px] text-[#6E6E73] font-medium mb-2">Language</p>
          <div className="flex gap-2">
            {LANGS.map((flag, i) => (
              <button
                key={LANG_CODES[i]}
                className={`w-10 h-10 rounded-xl text-xl ${user?.language === LANG_CODES[i] ? 'ring-2 ring-[#6C47FF]' : ''}`}
              >
                {flag}
              </button>
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
          <button onClick={() => tg?.openLink('https://t.me/imodelbot')}>Privacy</button>
          <span>·</span>
          <button onClick={() => tg?.openLink('https://t.me/imodelbot')}>Terms</button>
        </div>
      </div>
    </div>
  )
}
