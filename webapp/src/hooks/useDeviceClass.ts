import { useMemo } from 'react'

export type DeviceClass = 'low' | 'mid' | 'high'

export function useDeviceClass(): DeviceClass {
  return useMemo(() => {
    const cores = navigator.hardwareConcurrency ?? 4
    const mem = (navigator as { deviceMemory?: number }).deviceMemory ?? 4
    if (cores <= 2 || mem <= 1) return 'low'
    if (cores <= 4 || mem <= 2) return 'mid'
    return 'high'
  }, [])
}
