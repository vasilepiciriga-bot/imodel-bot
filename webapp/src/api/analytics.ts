import { api } from './client'

type Props = Record<string, string | number | boolean | null | undefined>

let _queue: Array<{ event: string; props: Props }> = []
let _flushing = false

async function _flush() {
  if (_flushing || !_queue.length) return
  _flushing = true
  const batch = _queue.splice(0)
  for (const { event, props } of batch) {
    try {
      await api.post('/api/v1/analytics/event', { event, props })
    } catch {
      // analytics failures are silent
    }
  }
  _flushing = false
}

export function track(event: string, props?: Props) {
  _queue.push({ event, props: props ?? {} })
  // Debounce flush — send after 300ms idle
  setTimeout(_flush, 300)
}
