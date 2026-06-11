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
  bot_link?: string
  gens_ok?: number
  payments?: number
  portfolio_public?: boolean
  portfolio_url?: string
  role?: string
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
  status: 'pending' | 'processing' | 'queued' | 'running' | 'done' | 'ready' | 'error' | 'failed'
  output_url?: string
  output_urls?: string[]
  hd_url?: string
  hd_job_id?: string
  preset_key?: string
  mode?: string
  photoshoot_mode?: string
  step_label?: string
  credit_cost?: number
  created_at: string
  original_url?: string
}

export type GenerationMode = 'portrait' | 'copy_scene' | 'face_swap'

export type PhotoshootModeKey =
  | 'everyday' | 'premium' | 'vogue' | 'ceo' | 'dating' | 'luxury' | 'custom'

export type PhotoshootBadge = 'popular' | 'best_quality' | 'for_business' | 'viral' | null

export interface PhotoshootMode {
  key: PhotoshootModeKey
  label: string
  label_en: string
  label_ru: string
  emoji: string
  credits: number
  n_generations: number
  select_best: number
  upscale: boolean
  is_premium: boolean
  requires_custom_prompt: boolean
  badge: PhotoshootBadge
  short_desc: string
}

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
