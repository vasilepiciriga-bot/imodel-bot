import { api, invalidateCache } from './client'
import type { UserProfile, Challenge, DailyBonusResult } from '../types'

/** Always fetch fresh — bypasses the SWR cache (used after purchases/mutations). */
export const getMe = () => api.get<UserProfile>('/api/v1/me')
export const getMeFresh = () => { invalidateCache('/api/v1/me'); return api.get<UserProfile>('/api/v1/me') }

export const createSession = () =>
  api.post<UserProfile>('/api/v1/webapp/session')

export const getChallenge = () =>
  api.get<Challenge>('/api/v1/profile/challenge')

export const claimDaily = () =>
  api.post<DailyBonusResult>('/api/v1/profile/daily')

export const getStats = () =>
  api.get<{ total_generated: number; streak: number; friends_invited: number }>('/api/v1/profile/stats')

export interface ReferralData {
  link: string
  invited_count: number
  credits_earned: number
  bonus_per_invite: number
  bonus_for_new: number
  next_milestone: number | null
  next_milestone_bonus: number
  milestones: Array<{ count: number; bonus: number; reached: boolean }>
}

export const getReferral = () => api.get<ReferralData>('/api/v1/referral')
