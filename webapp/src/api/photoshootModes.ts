import { api } from './client'
import type { PhotoshootMode } from '../types'

export const fetchPhotoshootModes = () =>
  api.get<{ modes: PhotoshootMode[] }>('/api/v1/photoshoot-modes')

const CACHE_KEY = 'photoshoot_modes_cache'
const TTL = 60 * 60 * 1000

export function getCachedModes(): PhotoshootMode[] | null {
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

export function setCachedModes(modes: PhotoshootMode[]) {
  localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: modes }))
}

export function clearModesCache() {
  localStorage.removeItem(CACHE_KEY)
}
