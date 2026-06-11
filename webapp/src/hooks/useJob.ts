import { useEffect, useRef } from 'react'
import { getGeneration } from '../api/generations'
import type { Generation } from '../types'

export function useJobPoller(
  jobId: string | null,
  onUpdate: (job: Generation) => void,
  intervalMs = 2000
) {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const job = await getGeneration(jobId)
        onUpdate(job)
        if (job.status === 'done' || job.status === 'error') {
          clearInterval(timerRef.current!)
          timerRef.current = null
        }
      } catch {
        // keep polling
      }
    }

    poll()
    timerRef.current = setInterval(poll, intervalMs)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [jobId, intervalMs]) // eslint-disable-line react-hooks/exhaustive-deps
}
