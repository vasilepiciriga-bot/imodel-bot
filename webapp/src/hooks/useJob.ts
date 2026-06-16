import { useEffect, useRef } from 'react'
import { getGeneration } from '../api/generations'
import type { Generation } from '../types'

const tg = window.Telegram?.WebApp

const TERMINAL = new Set(['done', 'ready', 'error', 'failed', 'cancelled'])

function sseUrl(jobId: string): string {
  return `/api/v1/generations/${jobId}/events?tma=${encodeURIComponent(tg?.initData ?? '')}`
}

export function useJobPoller(
  jobId: string | null,
  onUpdate: (job: Generation) => void,
  intervalMs = 2000
) {
  // Ref keeps the latest callback without triggering effect re-runs
  const onUpdateRef = useRef(onUpdate)
  onUpdateRef.current = onUpdate

  useEffect(() => {
    if (!jobId) return

    // ── SSE path ───────────────────────────────────────────────────────────
    if (typeof EventSource !== 'undefined' && tg?.initData) {
      const es = new EventSource(sseUrl(jobId))
      let settled = false

      es.onmessage = (event) => {
        try {
          const job = JSON.parse(event.data) as Generation & { error?: string }
          // Skip pure auth/routing error frames that have no job data
          if (job.error && !job.status) return
          onUpdateRef.current(job)
          if (TERMINAL.has(job.status)) {
            settled = true
            es.close()
          }
        } catch { /* ignore malformed frames */ }
      }

      es.addEventListener('done', () => {
        settled = true
        es.close()
      })

      es.onerror = () => {
        es.close()
        if (settled) return
        // SSE failed mid-stream — fetch current state once and stop
        getGeneration(jobId).then((job) => onUpdateRef.current(job)).catch(() => null)
      }

      return () => es.close()
    }

    // ── Polling fallback (no EventSource or no initData) ───────────────────
    let timer: ReturnType<typeof setInterval> | null = null
    let active = true

    const poll = async () => {
      if (!active) return
      try {
        const job = await getGeneration(jobId)
        onUpdateRef.current(job)
        if (TERMINAL.has(job.status)) {
          active = false
          if (timer) { clearInterval(timer); timer = null }
        }
      } catch { /* keep polling on transient errors */ }
    }

    poll()
    timer = setInterval(poll, intervalMs)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [jobId]) // onUpdate excluded — accessed via ref
}
