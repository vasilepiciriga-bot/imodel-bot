import { api } from './client'

export interface CaptionResult {
  captions: string[]
}

export const generateCaption = (style: string, mode: string) =>
  api.post<CaptionResult>('/api/v1/caption/generate', { style, mode })
