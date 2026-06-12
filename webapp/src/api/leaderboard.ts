import { api } from './client'

export interface LeaderboardEntry {
  rank: number
  display_name: string
  gens: number
  is_me: boolean
}

export interface LeaderboardData {
  entries: LeaderboardEntry[]
  period: '7d' | 'all'
  my_rank: number | null
  my_gens: number
  updated_at: number
}

export function getLeaderboard(): Promise<LeaderboardData> {
  return api.get<LeaderboardData>('/api/v1/leaderboard')
}

export interface MonthlyChallenge {
  active: boolean
  mode_key?: string
  mode_emoji?: string
  mode_label?: string
  name?: string
  prize_top1?: number
  prize_top2?: number
  prize_top3?: number
  month?: string
  days_left?: number
  total_participants?: number
  my_gens?: number
  my_rank?: number | null
  top3?: LeaderboardEntry[]
}

export function getMonthlyChallenge(): Promise<MonthlyChallenge> {
  return api.get<MonthlyChallenge>('/api/v1/challenge/monthly')
}
