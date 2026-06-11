import { api } from './client'

export interface QuestItem {
  id: string
  title: string
  icon: string
  type: 'daily' | 'milestone' | 'lifetime'
  target: number
  progress: number
  reward: number
  claimable: boolean
  claimed: boolean
}

export interface Achievement {
  id: string
  title: string
  icon: string
  desc: string
  unlocked: boolean
  unlocked_at: number | null
}

export const getQuests = () => api.get<{ quests: QuestItem[]; claimable: number }>('/api/v1/quests')

export const claimQuest = (questId: string) =>
  api.post<{ ok: boolean; credits_added: number; new_balance: number }>(`/api/v1/quests/${questId}/claim`)

export const getAchievements = () =>
  api.get<{ achievements: Achievement[]; newly_unlocked: string[] }>('/api/v1/achievements')

export const setLanguage = (language: string) =>
  api.post<{ ok: boolean; language: string }>('/api/v1/me/language', { language })

export const reactToPhoto = (jobId: string, emoji: string) =>
  api.post<{ ok: boolean; reactions: Record<string, number>; my_reaction: string | null }>(
    `/api/v1/gallery/${jobId}/react`,
    { emoji }
  )
