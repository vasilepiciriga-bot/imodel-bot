import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Users, Zap, TrendingUp, Radio, Search, Send, Plus, Minus, RefreshCw, ChevronDown, Layers, BarChart2, DollarSign, Award } from 'lucide-react'
import {
  getDashboard, lookupUser, grantCredits, sendUserMessage,
  getBroadcastStatus, sendBroadcast, cancelBroadcast, generatePresetThumbs,
  getFunnel, getExperimentResults, getRetention, getLTV, getQuality,
  type AdminDashboard, type AdminUser, type BroadcastStatus,
  type FunnelData, type ExperimentsData, type RetentionData, type LTVData, type QualityData,
} from '../api/admin'
import { track } from '../api/analytics'

const tg = window.Telegram?.WebApp

type AdminTab = 'dashboard' | 'users' | 'broadcast' | 'tools' | 'analytics' | 'retention' | 'ltv' | 'quality'

function timeAgo(ts: number): string {
  if (!ts) return 'never'
  const d = Math.max(0, Math.floor(Date.now() / 1000 - ts))
  if (d < 60) return `${d}s ago`
  if (d < 3600) return `${Math.floor(d / 60)}m ago`
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`
  return `${Math.floor(d / 86400)}d ago`
}

function MetricCard({ label, value, sub, accent = '#6C47FF' }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className="bg-white rounded-[16px] p-4 flex flex-col gap-1 shadow-sm border border-black/[0.05]">
      <p className="text-[11px] font-semibold text-[#6E6E73] uppercase tracking-wide">{label}</p>
      <p className="text-[26px] font-bold leading-none" style={{ color: accent }}>{value}</p>
      {sub && <p className="text-[11px] text-[#6E6E73]">{sub}</p>}
    </div>
  )
}

function PeriodRow({ label, data }: { label: string; data: { gens: number; payments: number; new_users: number; referrals: number } }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-[#F0F0F5] last:border-0">
      <span className="w-14 text-[12px] font-semibold text-[#6E6E73]">{label}</span>
      <div className="flex-1 grid grid-cols-4 gap-1 text-center">
        <div><p className="text-[14px] font-bold text-[#1D1D1F]">{data.gens}</p><p className="text-[9px] text-[#6E6E73]">gens</p></div>
        <div><p className="text-[14px] font-bold text-[#34C759]">{data.payments}</p><p className="text-[9px] text-[#6E6E73]">sales</p></div>
        <div><p className="text-[14px] font-bold text-[#6C47FF]">{data.new_users}</p><p className="text-[9px] text-[#6E6E73]">new</p></div>
        <div><p className="text-[14px] font-bold text-[#FF9500]">{data.referrals}</p><p className="text-[9px] text-[#6E6E73]">refs</p></div>
      </div>
    </div>
  )
}

// ─── Dashboard tab ────────────────────────────────────────────────────────────
function DashboardTab() {
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [showTop, setShowTop] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    getDashboard()
      .then(setData)
      .catch(() => null)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
        <RefreshCw size={24} className="text-[#6C47FF]" />
      </motion.div>
    </div>
  )

  if (!data) return (
    <div className="flex-1 flex items-center justify-center text-[#6E6E73]">Failed to load</div>
  )

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-4">
      <div className="flex items-center justify-between pt-2">
        <p className="text-[16px] font-bold text-[#1D1D1F]">Overview</p>
        <button onClick={load} className="p-1.5 rounded-full bg-[#F5F5F7]">
          <RefreshCw size={14} className="text-[#6E6E73]" />
        </button>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <MetricCard label="Total Users" value={data.users_total.toLocaleString()} />
        <MetricCard label="Active 24h" value={data.users_active_24h.toLocaleString()} accent="#34C759" />
        <MetricCard label="Online now" value={data.users_online_5m} sub="last 5 min" accent="#FF9500" />
        <MetricCard label="Total Gens" value={data.total_gens.toLocaleString()} />
      </div>

      {/* Period table */}
      <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05]">
        <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-3">Activity</p>
        <PeriodRow label="Today" data={data.today} />
        <PeriodRow label="7 days" data={data.week} />
        <PeriodRow label="30 days" data={data.month} />
      </div>

      {/* Broadcast status */}
      {data.broadcast_running && (
        <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/20 rounded-[14px] p-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#FF3B30] animate-pulse" />
          <p className="text-[13px] font-semibold text-[#FF3B30]">Broadcast is running</p>
        </div>
      )}

      {/* Top generators */}
      <div className="bg-white rounded-[16px] shadow-sm border border-black/[0.05] overflow-hidden">
        <button
          onClick={() => setShowTop(!showTop)}
          className="w-full flex items-center justify-between px-4 py-3"
        >
          <p className="text-[13px] font-semibold text-[#1D1D1F]">Top Generators (all time)</p>
          <motion.div animate={{ rotate: showTop ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronDown size={16} className="text-[#6E6E73]" />
          </motion.div>
        </button>
        <AnimatePresence>
          {showTop && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {data.top_gens.map((u, i) => (
                <div key={u.uid} className="flex items-center px-4 py-2.5 border-t border-[#F0F0F5]">
                  <span className="w-5 text-[12px] font-bold text-[#6E6E73]">#{i + 1}</span>
                  <div className="flex-1 min-w-0 ml-2">
                    <p className="text-[13px] font-semibold text-[#1D1D1F] truncate">
                      {u.username ? `@${u.username}` : `uid:${u.uid}`}
                    </p>
                    <p className="text-[10px] text-[#6E6E73]">{timeAgo(u.last_seen)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[13px] font-bold text-[#6C47FF]">{u.gens} gens</p>
                    {u.payments > 0 && <p className="text-[10px] text-[#34C759]">{u.payments} paid</p>}
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ─── Users tab ────────────────────────────────────────────────────────────────
function UsersTab() {
  const [query, setQuery] = useState('')
  const [user, setUser] = useState<AdminUser | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [creditDelta, setCreditDelta] = useState('')
  const [creditReason, setCreditReason] = useState('admin_grant')
  const [message, setMessage] = useState('')
  const [actionMsg, setActionMsg] = useState('')

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true); setError(''); setUser(null); setActionMsg('')
    try {
      const u = await lookupUser(query.trim())
      setUser(u)
      track('admin_user_lookup', { q: query.trim() })
    } catch {
      setError('User not found')
    } finally {
      setLoading(false)
    }
  }

  async function handleCredits(sign: 1 | -1) {
    if (!user || !creditDelta) return
    const delta = sign * Math.abs(parseInt(creditDelta, 10))
    if (!delta) return
    try {
      const res = await grantCredits(user.uid, delta, creditReason)
      setUser({ ...user, credits: res.after })
      setActionMsg(`✅ Credits: ${res.before} → ${res.after}`)
      tg?.HapticFeedback?.notificationOccurred('success')
    } catch {
      setActionMsg('❌ Failed')
    }
    setCreditDelta('')
  }

  async function handleSendMessage() {
    if (!user || !message.trim()) return
    try {
      await sendUserMessage(user.uid, message.trim())
      setActionMsg('✅ Message sent')
      setMessage('')
      tg?.HapticFeedback?.notificationOccurred('success')
    } catch {
      setActionMsg('❌ Failed to send')
    }
  }

  const planColor = (plan: string) => plan === 'free' ? '#6E6E73' : '#6C47FF'

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-3 pt-2">
      {/* Search */}
      <div className="flex gap-2">
        <input
          className="flex-1 px-3 py-2.5 rounded-[12px] bg-[#F5F5F7] text-[14px] outline-none border border-transparent focus:border-[#6C47FF]/40"
          placeholder="@username or uid"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <motion.button
          whileTap={{ scale: 0.94 }}
          onClick={handleSearch}
          className="px-4 py-2.5 rounded-[12px] bg-[#6C47FF] text-white"
        >
          <Search size={16} />
        </motion.button>
      </div>

      {loading && <p className="text-center text-[#6E6E73] text-[13px]">Searching…</p>}
      {error && <p className="text-center text-[#FF3B30] text-[13px]">{error}</p>}

      <AnimatePresence>
        {user && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-3"
          >
            {/* Profile card */}
            <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05]">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] flex items-center justify-center text-white font-bold text-[16px]">
                  {(user.username?.[0] || String(user.uid)[0]).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[15px] font-bold text-[#1D1D1F] truncate">
                    {user.username ? `@${user.username}` : `uid:${user.uid}`}
                  </p>
                  <p className="text-[11px] text-[#6E6E73]">UID: {user.uid} · {user.last_seen_ago}</p>
                </div>
                <span
                  className="px-2 py-0.5 rounded-full text-[11px] font-semibold text-white"
                  style={{ background: planColor(user.plan) }}
                >
                  {user.plan}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { v: user.credits, l: 'Credits' },
                  { v: user.gens_ok, l: 'Gens' },
                  { v: user.streak, l: 'Streak 🔥' },
                ].map(({ v, l }) => (
                  <div key={l} className="bg-[#F5F5F7] rounded-[10px] py-2">
                    <p className="text-[16px] font-bold text-[#1D1D1F]">{v}</p>
                    <p className="text-[10px] text-[#6E6E73]">{l}</p>
                  </div>
                ))}
              </div>
              {user.blocked && (
                <p className="mt-2 text-center text-[11px] text-[#FF3B30] font-semibold">⛔ Bot blocked</p>
              )}
            </div>

            {/* Grant credits */}
            <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05]">
              <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2.5">Adjust Credits</p>
              <div className="flex gap-2 mb-2">
                <input
                  className="flex-1 px-3 py-2 rounded-[10px] bg-[#F5F5F7] text-[14px] outline-none border border-transparent focus:border-[#6C47FF]/40"
                  placeholder="Amount"
                  type="number"
                  min="1"
                  value={creditDelta}
                  onChange={(e) => setCreditDelta(e.target.value)}
                />
                <input
                  className="flex-1 px-3 py-2 rounded-[10px] bg-[#F5F5F7] text-[13px] outline-none"
                  placeholder="Reason"
                  value={creditReason}
                  onChange={(e) => setCreditReason(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => handleCredits(1)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[10px] bg-[#34C759]/15 text-[#34C759] font-semibold text-[13px]"
                >
                  <Plus size={14} /> Add
                </motion.button>
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => handleCredits(-1)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-[10px] bg-[#FF3B30]/10 text-[#FF3B30] font-semibold text-[13px]"
                >
                  <Minus size={14} /> Deduct
                </motion.button>
              </div>
            </div>

            {/* Send message */}
            <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05]">
              <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2.5">Send Message</p>
              <textarea
                className="w-full px-3 py-2 rounded-[10px] bg-[#F5F5F7] text-[13px] outline-none resize-none border border-transparent focus:border-[#6C47FF]/40"
                rows={3}
                placeholder="Message text…"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={handleSendMessage}
                disabled={!message.trim()}
                className="mt-2 w-full py-2.5 rounded-[10px] bg-[#6C47FF] text-white text-[13px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-40"
              >
                <Send size={14} /> Send to user
              </motion.button>
            </div>

            {actionMsg && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center text-[13px] font-medium text-[#1D1D1F]"
              >
                {actionMsg}
              </motion.p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Broadcast tab ────────────────────────────────────────────────────────────
function BroadcastTab() {
  const [status, setStatus] = useState<BroadcastStatus | null>(null)
  const [segment, setSegment] = useState('')
  const [msgText, setMsgText] = useState('')
  const [campName, setCampName] = useState('')
  const [deepLink, setDeepLink] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState('')

  const load = useCallback(() => {
    getBroadcastStatus().then(setStatus).catch(() => null)
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (status && !segment) {
      const first = Object.keys(status.segments)[0]
      if (first) setSegment(first)
    }
  }, [status, segment])

  async function handleSend() {
    if (!segment || !msgText.trim() || sending) return
    setSending(true); setResult('')
    try {
      const res = await sendBroadcast(segment, msgText.trim(), campName.trim() || segment, deepLink.trim())
      setResult(`✅ Campaign "${res.campaign_id}" queued for ${res.size} users`)
      setMsgText(''); setCampName('')
      load()
      tg?.HapticFeedback?.notificationOccurred('success')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error'
      setResult(`❌ ${msg}`)
    } finally {
      setSending(false)
    }
  }

  async function handleCancel() {
    await cancelBroadcast()
    setResult('Campaign cancelled')
    load()
  }

  const isRunning = status?.running && (status.running as { status?: string }).status === 'running'
  const selectedSeg = status?.segments[segment]

  const segStatusColor = (s: string) => {
    if (s === 'done') return 'text-[#34C759]'
    if (s === 'running') return 'text-[#FF9500]'
    if (s === 'cancelled') return 'text-[#6E6E73]'
    return 'text-[#FF3B30]'
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-3 pt-2">
      {isRunning && (
        <div className="flex items-center justify-between bg-[#FF9500]/10 border border-[#FF9500]/20 rounded-[14px] p-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#FF9500] animate-pulse" />
            <p className="text-[13px] font-semibold text-[#FF9500]">Campaign running…</p>
          </div>
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={handleCancel}
            className="text-[12px] text-[#FF3B30] font-semibold px-2 py-1 rounded-[8px] bg-[#FF3B30]/10"
          >
            Cancel
          </motion.button>
        </div>
      )}

      {/* Segment picker */}
      {status && (
        <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05]">
          <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2.5">Segment</p>
          <div className="space-y-2">
            {Object.entries(status.segments).map(([key, seg]) => (
              <motion.button
                key={key}
                whileTap={{ scale: 0.98 }}
                onClick={() => setSegment(key)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-[10px] border-2 transition-colors ${
                  segment === key ? 'border-[#6C47FF] bg-[#6C47FF]/5' : 'border-transparent bg-[#F5F5F7]'
                }`}
              >
                <span className="text-[13px] font-medium text-[#1D1D1F]">{seg.desc}</span>
                <span className="text-[12px] font-semibold text-[#6C47FF]">{seg.size.toLocaleString()}</span>
              </motion.button>
            ))}
          </div>
          {selectedSeg && (
            <p className="mt-2 text-center text-[12px] text-[#6E6E73]">
              {selectedSeg.size.toLocaleString()} recipients
            </p>
          )}
        </div>
      )}

      {/* Compose */}
      <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05]">
        <p className="text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide mb-2.5">Message</p>
        <input
          className="w-full px-3 py-2 rounded-[10px] bg-[#F5F5F7] text-[13px] outline-none mb-2"
          placeholder="Campaign name (optional)"
          value={campName}
          onChange={(e) => setCampName(e.target.value)}
        />
        <textarea
          className="w-full px-3 py-2 rounded-[10px] bg-[#F5F5F7] text-[13px] outline-none resize-none border border-transparent focus:border-[#6C47FF]/40"
          rows={4}
          placeholder="Message text (Markdown OK)…"
          value={msgText}
          onChange={(e) => setMsgText(e.target.value)}
        />
        <input
          className="w-full mt-2 px-3 py-2 rounded-[10px] bg-[#F5F5F7] text-[13px] outline-none"
          placeholder="Deep link (optional, e.g. /start)"
          value={deepLink}
          onChange={(e) => setDeepLink(e.target.value)}
        />
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleSend}
          disabled={!msgText.trim() || !segment || sending || !!isRunning}
          className="mt-3 w-full py-3 rounded-[12px] bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] text-white text-[14px] font-semibold flex items-center justify-center gap-2 disabled:opacity-40"
        >
          <Radio size={15} />
          {sending ? 'Sending…' : `Broadcast to ${selectedSeg?.size?.toLocaleString() ?? '?'}`}
        </motion.button>
      </div>

      {result && (
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center text-[13px] font-medium text-[#1D1D1F]">
          {result}
        </motion.p>
      )}

      {/* History */}
      {status && status.history.length > 0 && (
        <div className="bg-white rounded-[16px] shadow-sm border border-black/[0.05] overflow-hidden">
          <p className="px-4 pt-3 pb-1 text-[12px] font-semibold text-[#6E6E73] uppercase tracking-wide">Recent Campaigns</p>
          {status.history.map((c) => (
            <div key={c.campaign_id} className="flex items-center px-4 py-2.5 border-t border-[#F0F0F5]">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-[#1D1D1F] truncate">{c.name}</p>
                <p className="text-[10px] text-[#6E6E73]">{c.segment} · {c.sent}/{c.total} sent</p>
              </div>
              <span className={`text-[11px] font-semibold capitalize ${segStatusColor(c.status)}`}>
                {c.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Tools tab ────────────────────────────────────────────────────────────────
function ToolsTab() {
  const [refUrl, setRefUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ queued: number; keys: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate() {
    setBusy(true)
    setResult(null)
    setError(null)
    try {
      const res = await generatePresetThumbs(refUrl.trim() || undefined)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-6 pt-3 space-y-4">
      <div className="bg-white rounded-[16px] p-4 shadow-sm border border-black/[0.05] space-y-3">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-[#6C47FF]" />
          <p className="text-[14px] font-bold text-[#1D1D1F]">Preset Thumbnails</p>
        </div>
        <p className="text-[12px] text-[#6E6E73] leading-relaxed">
          Generate preview images for all style presets using a reference face photo.
          Leave blank to use the default stock photo.
        </p>
        <input
          type="url"
          value={refUrl}
          onChange={(e) => setRefUrl(e.target.value)}
          placeholder="https://... (optional reference photo URL)"
          className="w-full px-3 py-2.5 rounded-[10px] bg-[#F5F5F7] text-[13px] text-[#1D1D1F] placeholder-[#AEAEB2] outline-none"
        />
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleGenerate}
          disabled={busy}
          className="w-full py-3 rounded-[12px] bg-[#6C47FF] text-white text-[14px] font-semibold disabled:opacity-50"
        >
          {busy ? 'Queuing...' : 'Generate All Thumbnails'}
        </motion.button>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3 rounded-[10px] bg-[#34C759]/10 border border-[#34C759]/30"
          >
            <p className="text-[13px] font-semibold text-[#34C759]">
              ✓ Queued {result.queued} presets
            </p>
            <p className="text-[11px] text-[#6E6E73] mt-0.5">
              Generation runs in background — refresh Styles in ~5 min.
            </p>
          </motion.div>
        )}
        {error && (
          <p className="text-[12px] text-[#FF3B30] font-medium">{error}</p>
        )}
      </div>
    </div>
  )
}


// ─── Analytics tab ────────────────────────────────────────────────────────────
function AnalyticsTab() {
  const [days, setDays] = useState(7)
  const [funnel, setFunnel] = useState<FunnelData | null>(null)
  const [experiments, setExperiments] = useState<ExperimentsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([getFunnel(days), getExperimentResults(days * 2)])
      .then(([f, e]) => { setFunnel(f); setExperiments(e) })
      .catch(() => null)
      .finally(() => setLoading(false))
  }, [days])

  function pct(v: number | null | undefined) {
    return v == null ? '—' : `${(v * 100).toFixed(1)}%`
  }
  function num(v: number | undefined) {
    return v == null ? '—' : v.toLocaleString()
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      {/* Period selector */}
      <div className="flex gap-2">
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold ${
              days === d ? 'bg-[#6C47FF] text-white' : 'bg-[#E8E8ED] text-[#6E6E73]'
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-[13px] text-[#6E6E73]">Loading…</p>
      ) : (
        <>
          {/* Funnel metrics */}
          <div className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
            <div className="px-4 py-3 border-b border-black/[0.04]">
              <p className="text-[13px] font-bold text-[#1D1D1F]">Funnel — last {funnel?.period_days}d</p>
            </div>
            <div className="divide-y divide-black/[0.04]">
              {[
                ['Generations started', num(funnel?.generation_started), null],
                ['Completions', num(funnel?.generation_completed), pct(funnel?.completion_rate)],
                ['Paywall hits', num(funnel?.paywall_hit), pct(funnel?.paywall_rate)],
                ['Purchases', num(funnel?.purchase_completed), pct(funnel?.purchase_rate)],
                ['Shares', num(funnel?.share_tapped), null],
                ['Nudge conversions', num(funnel?.nudge_converted), pct(funnel?.nudge_conversion_rate)],
                ['Upgrade sheet used', '—', pct(funnel?.upgrade_sheet_rate)],
                ['Unique generators', num(funnel?.unique_generators), null],
                ['Unique buyers', num(funnel?.unique_buyers), null],
              ].map(([label, val, rate]) => (
                <div key={String(label)} className="flex items-center justify-between px-4 py-2.5">
                  <span className="text-[12px] text-[#1D1D1F]">{label}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-semibold text-[#1D1D1F]">{val}</span>
                    {rate && <span className="text-[11px] text-[#34C759] font-medium">{rate}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Revenue by segment */}
          {funnel?.revenue_by_segment && Object.keys(funnel.revenue_by_segment).length > 0 && (
            <div className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
              <div className="px-4 py-3 border-b border-black/[0.04]">
                <p className="text-[13px] font-bold text-[#1D1D1F]">Revenue by segment · {funnel.total_stars.toLocaleString()}★ total</p>
              </div>
              {Object.entries(funnel.revenue_by_segment).map(([seg, data]) => (
                <div key={seg} className="flex items-center justify-between px-4 py-2.5 border-b border-black/[0.04] last:border-0">
                  <span className="text-[12px] text-[#1D1D1F] capitalize">{seg}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-[#6E6E73]">{data.purchases} purchases</span>
                    <span className="text-[12px] font-semibold text-[#FF9500]">{data.stars.toLocaleString()}★</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Experiment results */}
          {experiments && Object.entries(experiments.experiments).map(([expName, exp]) => (
            <div key={expName} className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
              <div className="px-4 py-3 border-b border-black/[0.04]">
                <p className="text-[13px] font-bold text-[#1D1D1F]">{expName}</p>
                <p className="text-[11px] text-[#6E6E73]">{exp.description} · metric: {exp.primary_metric}</p>
              </div>
              <div className="divide-y divide-black/[0.04]">
                {Object.entries(exp.variants).map(([variant, stats]) => {
                  const isWinner = stats.rate != null && Object.values(exp.variants).every(
                    (v) => v === stats || (v.rate ?? -1) <= (stats.rate ?? 0)
                  )
                  return (
                    <div key={variant} className="flex items-center justify-between px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className={`text-[12px] font-semibold ${isWinner ? 'text-[#34C759]' : 'text-[#1D1D1F]'}`}>
                          {variant} {isWinner && stats.rate != null ? '🏆' : ''}
                        </span>
                        <span className="text-[10px] text-[#6E6E73]">{stats.exposed} exposed</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-[#6E6E73]">{stats.converted} cvt</span>
                        <span className={`text-[12px] font-bold ${isWinner ? 'text-[#34C759]' : 'text-[#6C47FF]'}`}>
                          {pct(stats.rate)}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}


// ─── Retention tab ────────────────────────────────────────────────────────────
function RetentionTab() {
  const [data, setData] = useState<RetentionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [weeks, setWeeks] = useState(8)

  const load = useCallback((w: number) => {
    setLoading(true)
    getRetention(w).then(setData).catch(() => null).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(weeks) }, [weeks, load])

  function pctCell(v: number | null | undefined): JSX.Element {
    if (v == null) return <span className="text-[#C7C7CC]">—</span>
    const pct = Math.round(v * 100)
    const bg = v >= 0.5 ? '#34C759' : v >= 0.3 ? '#FF9500' : v >= 0.15 ? '#FF9500' : '#FF3B30'
    const opacity = 0.12 + v * 0.5
    return (
      <span
        className="inline-block px-1.5 py-0.5 rounded-[6px] text-[11px] font-bold"
        style={{ background: `${bg}${Math.round(opacity * 255).toString(16).padStart(2, '0')}`, color: bg }}
      >
        {pct}%
      </span>
    )
  }

  const agg = data?.aggregate
  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      {/* Period selector */}
      <div className="flex gap-2">
        {[4, 8, 12].map((w) => (
          <button key={w} onClick={() => setWeeks(w)}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold ${weeks === w ? 'bg-[#6C47FF] text-white' : 'bg-[#E8E8ED] text-[#6E6E73]'}`}>
            {w}w
          </button>
        ))}
      </div>

      {/* Aggregate cards */}
      {agg && (
        <div className="grid grid-cols-4 gap-2">
          {([['D1', agg.d1, '#34C759'], ['D7', agg.d7, '#6C47FF'], ['D14', agg.d14, '#FF9500'], ['D30', agg.d30, '#FF3B30']] as const).map(([label, val, color]) => (
            <div key={label} className="bg-white rounded-[14px] p-3 text-center border border-black/[0.05]">
              <p className="text-[10px] font-semibold text-[#6E6E73] uppercase">{label}</p>
              <p className="text-[20px] font-bold mt-0.5" style={{ color: val != null ? color : '#C7C7CC' }}>
                {val != null ? `${Math.round(val * 100)}%` : '—'}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Cohort heatmap */}
      {loading ? (
        <p className="text-[13px] text-[#6E6E73]">Loading…</p>
      ) : data && data.cohorts.length > 0 ? (
        <div className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
          <div className="px-4 py-3 border-b border-black/[0.04]">
            <p className="text-[13px] font-bold text-[#1D1D1F]">Cohort retention heatmap</p>
            <p className="text-[11px] text-[#6E6E73]">Users returning after joining</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-black/[0.04]">
                  <th className="text-left px-4 py-2 text-[#6E6E73] font-semibold">Cohort</th>
                  <th className="px-3 py-2 text-[#6E6E73] font-semibold">Size</th>
                  <th className="px-3 py-2 text-[#34C759] font-semibold">D1</th>
                  <th className="px-3 py-2 text-[#6C47FF] font-semibold">D7</th>
                  <th className="px-3 py-2 text-[#FF9500] font-semibold">D14</th>
                  <th className="px-3 py-2 text-[#FF3B30] font-semibold">D30</th>
                </tr>
              </thead>
              <tbody>
                {data.cohorts.map((c) => (
                  <tr key={c.week} className="border-b border-black/[0.03] last:border-0">
                    <td className="px-4 py-2.5 font-medium text-[#1D1D1F]">{c.week}</td>
                    <td className="px-3 py-2.5 text-center text-[#6E6E73]">{c.size}</td>
                    <td className="px-3 py-2.5 text-center">{pctCell(c.d1)}</td>
                    <td className="px-3 py-2.5 text-center">{pctCell(c.d7)}</td>
                    <td className="px-3 py-2.5 text-center">{pctCell(c.d14)}</td>
                    <td className="px-3 py-2.5 text-center">{pctCell(c.d30)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="text-[13px] text-[#6E6E73]">No cohort data yet — needs DB events.</p>
      )}
    </div>
  )
}


// ─── LTV tab ──────────────────────────────────────────────────────────────────
function LTVTab() {
  const [data, setData] = useState<LTVData | null>(null)
  const [loading, setLoading] = useState(true)
  const [weeks, setWeeks] = useState(8)

  const load = useCallback((w: number) => {
    setLoading(true)
    getLTV(w).then(setData).catch(() => null).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(weeks) }, [weeks, load])

  const agg = data?.aggregate
  const maxStars = data ? Math.max(...data.cohorts.map((c) => c.stars_total), 1) : 1

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      <div className="flex gap-2">
        {[4, 8, 12].map((w) => (
          <button key={w} onClick={() => setWeeks(w)}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold ${weeks === w ? 'bg-[#6C47FF] text-white' : 'bg-[#E8E8ED] text-[#6E6E73]'}`}>
            {w}w
          </button>
        ))}
      </div>

      {/* KPI cards */}
      {agg && (
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-white rounded-[14px] p-3 border border-black/[0.05]">
            <p className="text-[10px] font-semibold text-[#6E6E73] uppercase">Avg ARPU D30</p>
            <p className="text-[22px] font-bold text-[#FF9500] mt-0.5">
              {agg.avg_arpu_30d != null ? `${agg.avg_arpu_30d}★` : '—'}
            </p>
            <p className="text-[10px] text-[#6E6E73]">stars per user in first 30d</p>
          </div>
          <div className="bg-white rounded-[14px] p-3 border border-black/[0.05]">
            <p className="text-[10px] font-semibold text-[#6E6E73] uppercase">Avg Conversion</p>
            <p className="text-[22px] font-bold text-[#34C759] mt-0.5">
              {agg.avg_conversion != null ? `${Math.round(agg.avg_conversion * 100)}%` : '—'}
            </p>
            <p className="text-[10px] text-[#6E6E73]">users who ever purchased</p>
          </div>
        </div>
      )}

      {/* Cohort LTV table */}
      {loading ? (
        <p className="text-[13px] text-[#6E6E73]">Loading…</p>
      ) : data && data.cohorts.length > 0 ? (
        <div className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
          <div className="px-4 py-3 border-b border-black/[0.04]">
            <p className="text-[13px] font-bold text-[#1D1D1F]">Cohort LTV</p>
            <p className="text-[11px] text-[#6E6E73]">Revenue generated per acquisition cohort</p>
          </div>
          <div className="divide-y divide-black/[0.03]">
            {data.cohorts.map((c) => {
              const barW = maxStars > 0 ? Math.round((c.stars_total / maxStars) * 100) : 0
              return (
                <div key={c.week} className="px-4 py-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[12px] font-semibold text-[#1D1D1F]">{c.week}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] text-[#6E6E73]">{c.size} users · {c.buyers} paid</span>
                      <span className="text-[12px] font-bold text-[#FF9500]">{c.stars_total.toLocaleString()}★</span>
                    </div>
                  </div>
                  {/* Revenue bar */}
                  <div className="h-1.5 bg-[#F0F0F5] rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${barW}%` }}
                      transition={{ duration: 0.6, ease: 'easeOut' }}
                      className="h-full rounded-full bg-gradient-to-r from-[#FF9500] to-[#FF2D78]"
                    />
                  </div>
                  {/* ARPU row */}
                  <div className="flex gap-3 mt-1.5">
                    {c.arpu_7d != null && (
                      <span className="text-[10px] text-[#6C47FF]">D7 ARPU: {c.arpu_7d}★</span>
                    )}
                    {c.arpu_30d != null && (
                      <span className="text-[10px] text-[#FF9500]">D30 ARPU: {c.arpu_30d}★</span>
                    )}
                    {c.conversion != null && (
                      <span className="text-[10px] text-[#34C759]">Conv: {Math.round(c.conversion * 100)}%</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <p className="text-[13px] text-[#6E6E73]">No LTV data yet — needs purchase events.</p>
      )}
    </div>
  )
}


// ─── Quality Tab ───────────────────────────────────────────────────────────────
function QualityTab() {
  const [days, setDays] = useState(14)
  const [data, setData] = useState<QualityData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getQuality(days).then(setData).catch(() => null).finally(() => setLoading(false))
  }, [days])

  const maxScore = data && data.modes.length > 0
    ? Math.max(...data.modes.map((m) => m.avg_winner_score), 1)
    : 100

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      <div className="flex gap-2">
        {[7, 14, 30].map((d) => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold ${
              days === d ? 'bg-[#6C47FF] text-white' : 'bg-[#E8E8ED] text-[#6E6E73]'
            }`}>
            {d}d
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-[13px] text-[#6E6E73]">Loading…</p>
      ) : (
        <>
          {/* Vision judge health */}
          <div className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
            <div className="px-4 py-3 border-b border-black/[0.04]">
              <p className="text-[13px] font-bold text-[#1D1D1F]">Vision Judge — all-time</p>
            </div>
            <div className="px-4 py-3 grid grid-cols-4 gap-2">
              {([
                { label: 'OK',   val: data?.judge_health.ok   ?? 0, color: '#34C759' },
                { label: 'Fail', val: data?.judge_health.fail ?? 0, color: '#FF3B30' },
                { label: 'Skip', val: data?.judge_health.skip ?? 0, color: '#6E6E73' },
                { label: 'Disq', val: data?.judge_health.disqualified ?? 0, color: '#FF9500' },
              ] as const).map(({ label, val, color }) => (
                <div key={label} className="flex flex-col items-center gap-0.5 p-2 rounded-[10px] bg-[#F5F5F7]">
                  <span className="text-[15px] font-black" style={{ color }}>{val.toLocaleString()}</span>
                  <span className="text-[10px] text-[#6E6E73] font-medium">{label}</span>
                </div>
              ))}
            </div>
            {data?.judge_health.ok_rate != null && (
              <div className="px-4 pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 rounded-full bg-[#E8E8ED] overflow-hidden">
                    <div className="h-full rounded-full bg-[#34C759]"
                      style={{ width: `${(data.judge_health.ok_rate * 100).toFixed(0)}%` }} />
                  </div>
                  <span className="text-[11px] text-[#34C759] font-semibold">
                    {(data.judge_health.ok_rate * 100).toFixed(1)}% success rate
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Per-mode winner scores */}
          {data && data.modes.length > 0 ? (
            <div className="rounded-[16px] bg-white border border-black/[0.06] overflow-hidden">
              <div className="px-4 py-3 border-b border-black/[0.04]">
                <p className="text-[13px] font-bold text-[#1D1D1F]">Winner Score by Mode · last {data.period_days}d</p>
                <p className="text-[11px] text-[#6E6E73]">Avg top-selected candidate score (0–100)</p>
              </div>
              <div className="divide-y divide-black/[0.04]">
                {data.modes.map((m) => {
                  const barPct = maxScore > 0 ? Math.round((m.avg_winner_score / maxScore) * 100) : 0
                  return (
                    <div key={m.mode} className="px-4 py-2.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[12px] font-semibold text-[#1D1D1F] capitalize">{m.mode}</span>
                        <div className="flex items-center gap-2.5">
                          <span className="text-[11px] text-[#6E6E73]">{m.count} gens</span>
                          <span className="text-[13px] font-bold text-[#6C47FF]">{m.avg_winner_score}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-[#E8E8ED] overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${barPct}%` }}
                            transition={{ duration: 0.5, ease: 'easeOut' }}
                            className="h-full rounded-full bg-gradient-to-r from-[#6C47FF] to-[#FF2D78]"
                          />
                        </div>
                        <span className="text-[10px] text-[#6E6E73] w-20 text-right shrink-0">
                          all avg: {m.avg_all_score}
                        </span>
                      </div>
                      {m.avg_candidates_total > 1 && (
                        <p className="text-[10px] text-[#6E6E73] mt-0.5">
                          {m.avg_candidates_ok}/{m.avg_candidates_total} candidates survived
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <p className="text-[13px] text-[#6E6E73]">No quality data yet — needs generation events with scores.</p>
          )}
        </>
      )}
    </div>
  )
}


// ─── Main Admin screen ─────────────────────────────────────────────────────────
export default function Admin() {
  const [tab, setTab] = useState<AdminTab>('dashboard')

  useEffect(() => {
    track('admin_panel_opened', { tab })
  }, [])

  const tabs: { key: AdminTab; label: string; icon: typeof Users }[] = [
    { key: 'dashboard',  label: 'Dash',      icon: TrendingUp },
    { key: 'users',      label: 'Users',     icon: Users },
    { key: 'broadcast',  label: 'Broadcast', icon: Radio },
    { key: 'tools',      label: 'Tools',     icon: Layers },
    { key: 'analytics',  label: 'Funnel',    icon: Zap },
    { key: 'retention',  label: 'Retention', icon: BarChart2 },
    { key: 'ltv',        label: 'LTV',       icon: DollarSign },
    { key: 'quality',    label: 'Quality',   icon: Award },
  ]

  return (
    <div className="flex flex-col h-full bg-[#F5F5F7]">
      {/* Header */}
      <div className="px-4 pt-4 pb-2 flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-[#1D1D1F]">⚙️ Admin</h1>
          <p className="text-[12px] text-[#6E6E73]">iModel control panel</p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FF3B30]/10 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-[#FF3B30]" />
          <span className="text-[11px] font-semibold text-[#FF3B30]">Admin</span>
        </div>
      </div>

      {/* Tab bar — scrollable for 7 tabs */}
      <div className="flex gap-1.5 mx-4 mb-1 overflow-x-auto no-scrollbar">
        {tabs.map(({ key, label, icon: Icon }) => (
          <motion.button
            key={key}
            whileTap={{ scale: 0.97 }}
            onClick={() => setTab(key)}
            className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-[10px] text-[12px] font-semibold transition-colors ${
              tab === key ? 'bg-[#6C47FF] text-white' : 'bg-[#E8E8ED] text-[#6E6E73]'
            }`}
          >
            <Icon size={13} />
            {label}
          </motion.button>
        ))}
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.18 }}
          className="flex-1 flex flex-col overflow-hidden"
        >
          {tab === 'dashboard'  && <DashboardTab />}
          {tab === 'users'      && <UsersTab />}
          {tab === 'broadcast'  && <BroadcastTab />}
          {tab === 'tools'      && <ToolsTab />}
          {tab === 'analytics'  && <AnalyticsTab />}
          {tab === 'retention'  && <RetentionTab />}
          {tab === 'ltv'        && <LTVTab />}
          {tab === 'quality'    && <QualityTab />}
        </motion.div>
      </AnimatePresence>

      {/* Zap icon decoration */}
      <div className="flex justify-center pb-3 pt-1">
        <Zap size={12} className="text-[#C7C7CC]" />
      </div>
    </div>
  )
}
