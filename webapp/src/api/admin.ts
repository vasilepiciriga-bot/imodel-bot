import { api } from './client'

export interface AdminDashboard {
  users_total: number
  users_active_24h: number
  users_active_7d: number
  users_online_5m: number
  total_gens: number
  total_payments: number
  today: PeriodMetrics
  week: PeriodMetrics
  month: PeriodMetrics
  top_gens: TopUser[]
  broadcast_running: boolean
  broadcast_history: BroadcastEntry[]
}

export interface PeriodMetrics {
  gens: number
  payments: number
  new_users: number
  referrals: number
}

export interface TopUser {
  uid: number
  username: string
  gens: number
  payments: number
  last_seen: number
}

export interface AdminUser {
  uid: number
  username: string
  credits: number
  plan: string
  streak: number
  gens_ok: number
  payments: number
  language: string
  unlocked_packs: string[]
  last_seen: number
  last_seen_ago: string
  blocked: boolean
  is_free: boolean
}

export interface BroadcastEntry {
  campaign_id: string
  name: string
  segment: string
  total: number
  sent: number
  failed: number
  blocked: number
  status: string
  started_at: number
  finished_at: number | null
}

export interface BroadcastStatus {
  running: Record<string, unknown>
  history: BroadcastEntry[]
  segments: Record<string, { desc: string; size: number }>
}

export const getDashboard = () =>
  api.get<AdminDashboard>('/api/v1/admin/dashboard')

export const lookupUser = (q: string) =>
  api.get<AdminUser>(`/api/v1/admin/user?q=${encodeURIComponent(q)}`)

export const grantCredits = (uid: number, delta: number, reason = 'admin_grant') =>
  api.post<{ uid: number; before: number; after: number; delta: number }>(
    '/api/v1/admin/user/credits',
    { uid, delta, reason },
  )

export const sendUserMessage = (uid: number, text: string) =>
  api.post<{ sent: boolean }>('/api/v1/admin/user/message', { uid, text })

export const getBroadcastStatus = () =>
  api.get<BroadcastStatus>('/api/v1/admin/broadcast')

export const sendBroadcast = (segment: string, message: string, name: string, deep_link = '') =>
  api.post<{ campaign_id: string; size: number }>(
    '/api/v1/admin/broadcast',
    { segment, message, name, deep_link },
  )

export const cancelBroadcast = () =>
  fetch('/api/v1/admin/broadcast', {
    method: 'DELETE',
    headers: {
      Authorization: `tma ${window.Telegram?.WebApp?.initData ?? ''}`,
    },
  }).then((r) => r.json())

export const generatePresetThumbs = (reference_url?: string) =>
  api.post<{ queued: number; keys: string[] }>(
    '/api/v1/admin/generate-preset-thumbs',
    reference_url ? { reference_url } : {},
  )
