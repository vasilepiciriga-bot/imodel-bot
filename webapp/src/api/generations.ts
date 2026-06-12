import { api } from './client'
import type { Generation } from '../types'

interface CreateParams {
  image_b64: string
  prompt?: string
  preset_key?: string
  age_key?: string
  mode?: string
  style_b64?: string
  photoshoot_mode?: string
  custom_desc?: string
  style_variant?: string
  lang?: string
}

export const createGeneration = (params: CreateParams) =>
  api.post<{ job_id: string; credit_cost: number; photoshoot_mode: string }>('/api/v1/generations', params)

export const createBatch = (params: CreateParams) =>
  api.post<{ job_ids: string[] }>('/api/v1/generations/batch', params)

export const getGeneration = (jobId: string) =>
  api.get<Generation>(`/api/v1/generations/${jobId}`)

export const requestHD = (jobId: string) =>
  api.post<{ job_id: string }>(`/api/v1/generations/${jobId}/hd`)

export const getGallery = () =>
  api.get<{ items: Generation[] }>('/api/v1/gallery')

const GALLERY_KEY = 'gallery_cache'
const TTL = 5 * 60 * 1000

export function getCachedGallery(): Generation[] | null {
  try {
    const raw = localStorage.getItem(GALLERY_KEY)
    if (!raw) return null
    const { ts, data } = JSON.parse(raw)
    if (Date.now() - ts > TTL) return null
    return data
  } catch {
    return null
  }
}

export function setCachedGallery(items: Generation[]) {
  localStorage.setItem(GALLERY_KEY, JSON.stringify({ ts: Date.now(), data: items }))
}

export const deletePhoto = (jobId: string) =>
  api.delete<{ ok: boolean }>(`/api/v1/gallery/${jobId}`)
