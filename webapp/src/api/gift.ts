import { api } from './client'

export interface GiftResult {
  code: string
  credits: number
  link: string
}

export const createGift = (credits: number) =>
  api.post<GiftResult>('/api/v1/gift/create', { credits })
