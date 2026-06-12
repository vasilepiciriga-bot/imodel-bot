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

export interface FunnelData {
  period_days: number
  generation_started: number
  generation_completed: number
  paywall_hit: number
  purchase_completed: number
  share_tapped: number
  nudge_converted: number
  completion_rate: number | null
  paywall_rate: number | null
  purchase_rate: number | null
  nudge_conversion_rate: number | null
  upgrade_sheet_rate: number | null
  total_stars: number
  revenue_by_segment: Record<string, { purchases: number; stars: number }>
  unique_generators: number
  unique_buyers: number
}

export interface ExperimentVariantStats {
  exposed: number
  converted: number
  rate: number | null
}

export interface ExperimentResult {
  description: string
  primary_metric: string
  exposure_event: string
  variants: Record<string, ExperimentVariantStats>
}

export interface ExperimentsData {
  period_days: number
  experiments: Record<string, ExperimentResult>
}

export const getFunnel = (days = 7) =>
  api.get<FunnelData>(`/api/v1/analytics/funnel?days=${days}`)

export const getExperimentResults = (days = 14) =>
  api.get<ExperimentsData>(`/api/v1/analytics/experiments?days=${days}`)

export interface RetentionCohort {
  week: string
  size: number
  d1: number | null
  d7: number | null
  d14: number | null
  d30: number | null
}

export interface RetentionData {
  cohorts: RetentionCohort[]
  aggregate: { d1: number | null; d7: number | null; d14: number | null; d30: number | null }
}

export interface LTVCohort {
  week: string
  size: number
  stars_7d: number | null
  arpu_7d: number | null
  stars_30d: number | null
  arpu_30d: number | null
  stars_total: number
  buyers: number
  conversion: number | null
}

export interface LTVData {
  cohorts: LTVCohort[]
  aggregate: { avg_arpu_30d: number | null; avg_conversion: number | null }
}

export const getRetention = (weeks = 8) =>
  api.getUncached<RetentionData>(`/api/v1/analytics/retention?weeks=${weeks}`)

export const getLTV = (weeks = 8) =>
  api.getUncached<LTVData>(`/api/v1/analytics/ltv?weeks=${weeks}`)

export interface QualityMode {
  mode: string
  count: number
  avg_winner_score: number
  avg_all_score: number
  avg_candidates_ok: number
  avg_candidates_total: number
}

export interface QualityData {
  period_days: number
  modes: QualityMode[]
  judge_health: {
    ok: number
    fail: number
    skip: number
    disqualified: number
    total: number
    ok_rate: number | null
    fail_rate: number | null
  }
}

export const getQuality = (days = 14) =>
  api.getUncached<QualityData>(`/api/v1/analytics/quality?days=${days}`)
