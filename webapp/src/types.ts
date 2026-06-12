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
  plan: 'free' | 'pro' | 'creator' | 'elite' | 'sub_weekly' | 'weekly'
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
  last_gen_at?: number | null
  can_claim_daily?: boolean
  next_daily_credits?: number
  first_seen?: number | null
  recent_presets?: string[]
  recent_modes?: string[]
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
  thumbnail_url?: string
  votes?: number
  creator_name?: string
  creator_uid?: number
  my_vote?: boolean
  created_at?: number
  personalized_score?: number
  usage_7d?: number
  is_new?: boolean
}

export interface Generation {
  job_id: string
  status: 'pending' | 'processing' | 'queued' | 'running' | 'done' | 'ready' | 'error' | 'failed'
  output_url?: string
  output_urls?: string[]
  hd_url?: string
  hd_job_id?: string
  error?: string
  preset_key?: string
  mode?: string
  photoshoot_mode?: string
  step_label?: string
  credit_cost?: number
  created_at: string
  original_url?: string
  candidates_done?: number
  candidates_total?: number
}

export type GenerationMode = 'portrait' | 'copy_scene' | 'copy_image'

export type PhotoshootModeKey =
  | 'everyday' | 'premium' | 'vogue' | 'ceo' | 'dating' | 'luxury' | 'custom'

export type PhotoshootBadge = 'popular' | 'best_quality' | 'for_business' | 'viral' | null

export interface StyleVariant {
  label: string
  label_en: string
  label_ru: string
}

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
  style_variants: Record<string, StyleVariant>
}

export interface IdentityPassport {
  detected: boolean
  gender: string
  age_range: string
  skin_tone: string
  hair_color: string
  identity_layer: string
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
  participants_today?: number
}

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

export interface DailyBonusResult {
  gens_added: number
  streak: number
  credits: number
  next_at?: number
  milestone_bonus?: number
  phase?: number  // 0=generous, 1=normal, 2=reduced, 3=minimal
}
