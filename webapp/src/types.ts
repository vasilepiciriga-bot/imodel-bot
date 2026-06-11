export interface TelegramUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
  photo_url?: string
}

export interface UserProfile {
  uid: number
  credits: number
  plan: 'free' | 'pro' | 'elite' | 'sub_weekly'
  plan_expiry?: string
  streak: number
  total_generated: number
  friends_invited: number
  language: string
  unlocked_packs: string[]
  age_pack: boolean
}

export interface Preset {
  key: string
  label: string
  category: string
  is_premium: boolean
  pack_id?: string
  locked?: boolean
  emoji: string
  prompt?: string
}

export interface Generation {
  job_id: string
  status: 'pending' | 'processing' | 'done' | 'error'
  output_url?: string
  hd_url?: string
  preset_key?: string
  mode?: string
  created_at: string
  original_url?: string
}

export type GenerationMode = 'portrait' | 'copy_scene' | 'face_swap'

export interface ShopItem {
  id: string
  label: string
  stars: number
  credits?: number
  type: 'pack' | 'subscription' | 'one_time'
}

export interface Challenge {
  preset_key: string
  label: string
  bonus_credits: number
  date: string
}

export interface DailyBonusResult {
  gens_added: number
  streak: number
  credits: number
  next_at?: number
}
