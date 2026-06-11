import { api } from './client'

export type Assignments = Record<string, string>

let _cache: Assignments | null = null

export async function getExperiments(): Promise<Assignments> {
  if (_cache) return _cache
  try {
    const { assignments } = await api.get<{ assignments: Assignments }>('/api/v1/experiments')
    _cache = assignments
    return assignments
  } catch {
    return {}
  }
}

export function getVariantSync(experiment: string): string {
  return _cache?.[experiment] ?? 'control'
}
