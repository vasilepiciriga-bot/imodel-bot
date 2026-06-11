import { useEffect, useState } from 'react'
import { getExperiments } from '../api/experiments'

export function useExperiment(name: string): string {
  const [variant, setVariant] = useState('control')
  useEffect(() => {
    getExperiments().then((a) => setVariant(a[name] ?? 'control')).catch(() => null)
  }, [name])
  return variant
}
