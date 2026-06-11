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
