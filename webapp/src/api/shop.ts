import { api } from './client'

export interface SubItem { id: string; label?: string; plan: string; stars: number; credits: number; period: string; active: boolean }

export interface ShopData {
  subscriptions: SubItem[]
  annual_subscriptions?: SubItem[]
  packs: Array<{ id: string; label: string; stars: number; credits: number; badge?: string | null }>
  style_packs: Array<{ id: string; label: string; stars: number; styles_count: number; unlocked: boolean }>
  preset_packs: Array<{ id: string; label: string; emoji: string; stars: number; presets_count: number; unlocked: boolean }>
  subscription: null | { plan: string; expiry: string }
  unlocked_packs: string[]
  age_pack_owned: boolean
  credits: number
  banner: string | null
  subscription_features: Record<string, string[]>
  bundle: null | {
    id: string
    stars: number
    credits: number
    label: string
    includes: string[]
    expires_at: number
  }
}

export const setAutoRecharge = (pack: string, threshold: number, enabled: boolean) =>
  api.post<{ ok: boolean }>('/api/v1/auto-recharge', { pack, threshold, enabled })

export const createGiftSub = () =>
  api.post<{ ok: boolean; share_link: string; gift_days: number; gifter_bonus: number }>('/api/v1/gift/sub')

export const getShop = () => api.get<ShopData>('/api/v1/shop')

export const createInvoice = (item_id: string) =>
  api.post<{ invoice_url: string }>('/api/v1/shop/invoice', { item_id })

export const unlockStylePack = (pack_id: string) =>
  api.post<{ ok: boolean }>('/api/v1/style-packs/unlock', { pack_id })
