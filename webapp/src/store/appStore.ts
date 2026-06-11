import { create } from 'zustand'
import type { UserProfile, Preset, Generation, GenerationMode } from '../types'

type Tab = 'studio' | 'styles' | 'gallery' | 'shop' | 'profile'

interface AppState {
  tab: Tab
  setTab: (tab: Tab) => void

  user: UserProfile | null
  setUser: (user: UserProfile) => void
  updateCredits: (credits: number) => void

  selfieB64: string | null
  selfiePreview: string | null
  setSelfie: (b64: string, preview: string) => void
  clearSelfie: () => void

  activePreset: Preset | null
  setActivePreset: (preset: Preset | null) => void

  mode: GenerationMode
  setMode: (mode: GenerationMode) => void

  hdEnabled: boolean
  toggleHd: () => void
  batchEnabled: boolean
  toggleBatch: () => void

  currentJob: Generation | null
  setCurrentJob: (job: Generation | null) => void

  batchJobs: Generation[]
  setBatchJobs: (jobs: Generation[]) => void

  gallery: Generation[]
  setGallery: (items: Generation[]) => void
  prependGallery: (item: Generation) => void
}

export const useAppStore = create<AppState>((set) => ({
  tab: 'studio',
  setTab: (tab) => set({ tab }),

  user: null,
  setUser: (user) => set({ user }),
  updateCredits: (credits) => set((s) => s.user ? { user: { ...s.user, credits } } : {}),

  selfieB64: null,
  selfiePreview: null,
  setSelfie: (b64, preview) => set({ selfieB64: b64, selfiePreview: preview }),
  clearSelfie: () => set({ selfieB64: null, selfiePreview: null }),

  activePreset: null,
  setActivePreset: (preset) => set({ activePreset: preset }),

  mode: 'portrait',
  setMode: (mode) => set({ mode }),

  hdEnabled: false,
  toggleHd: () => set((s) => ({ hdEnabled: !s.hdEnabled })),
  batchEnabled: false,
  toggleBatch: () => set((s) => ({ batchEnabled: !s.batchEnabled })),

  currentJob: null,
  setCurrentJob: (job) => set({ currentJob: job }),

  batchJobs: [],
  setBatchJobs: (jobs) => set({ batchJobs: jobs }),

  gallery: [],
  setGallery: (items) => set({ gallery: items }),
  prependGallery: (item) => set((s) => ({ gallery: [item, ...s.gallery] })),
}))
