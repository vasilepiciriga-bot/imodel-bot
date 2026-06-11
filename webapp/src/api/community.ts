import { api } from './client'
import type { Preset } from '../types'

export const shareToCommunity = (job_id: string, label: string) =>
  api.post<{ ok: boolean; key: string; already_shared: boolean }>('/api/v1/community/share', { job_id, label })

export const getCommunityPresets = (sort: 'top' | 'new' = 'top') =>
  api.get<{ presets: Preset[] }>(`/api/v1/community?sort=${sort}`)

export const voteForPreset = (key: string) =>
  api.post<{ votes: number; my_vote: boolean }>(`/api/v1/community/${key}/vote`)

export const deleteCommunityPreset = (key: string) =>
  api.delete<{ ok: boolean }>(`/api/v1/community/${key}`)
