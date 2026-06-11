import { api } from './client'
import type { UserProfile, Challenge, DailyBonusResult } from '../types'

export const getMe = () => api.get<UserProfile>('/api/v1/me')

export const createSession = () =>
  api.post<UserProfile>('/api/v1/webapp/session')

export const getChallenge = () =>
  api.get<Challenge>('/api/v1/profile/challenge')

export const claimDaily = () =>
  api.post<DailyBonusResult>('/api/v1/profile/daily')

export const getStats = () =>
  api.get<{ total_generated: number; streak: number; friends_invited: number }>('/api/v1/profile/stats')
