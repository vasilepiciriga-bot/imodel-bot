import { api } from './client'
import type { Preset } from '../types'

const CACHE_KEY = 'presets_cache'
const TTL = 5 * 60 * 1000

export const fetchPresets = () =>
  api.get<{ presets: Preset[] }>('/api/v1/presets')

export function getCachedPresets(): Preset[] | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const { ts, data } = JSON.parse(raw)
    if (Date.now() - ts > TTL) return null
    return data
  } catch {
    return null
  }
}

export function setCachedPresets(presets: Preset[]) {
  localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: presets }))
}
