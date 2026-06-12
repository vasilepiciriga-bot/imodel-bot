const tg = window.Telegram?.WebApp

// GET cache: path → { data, ts, inflight }
const _cache = new Map<string, { data: unknown; ts: number }>()
const _inflight = new Map<string, Promise<unknown>>()

// TTLs (ms) for stale-while-revalidate — zero means no caching
const GET_TTL: Record<string, number> = {
  '/api/v1/me':      30_000,   // 30 s
  '/api/v1/presets': 120_000,  // 2 min
  '/api/v1/photoshoot-modes': 300_000, // 5 min
}

function getToken(): string {
  return tg?.initData ?? ''
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `tma ${getToken()}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(err.detail ?? 'Request failed'), { status: res.status, data: err })
  }
  return res.json()
}

async function cachedGet<T>(path: string): Promise<T> {
  const ttl = GET_TTL[path] ?? 0
  const entry = _cache.get(path)
  const now = Date.now()

  if (entry && now - entry.ts < ttl) {
    // Cache hit — return immediately, revalidate in background if past 80% of TTL
    if (now - entry.ts > ttl * 0.8) {
      void revalidate(path)
    }
    return entry.data as T
  }

  // Deduplicate concurrent requests for the same path
  const existing = _inflight.get(path)
  if (existing) return existing as Promise<T>

  const req = request<T>('GET', path).then((data) => {
    _cache.set(path, { data, ts: Date.now() })
    _inflight.delete(path)
    return data
  }).catch((err) => {
    _inflight.delete(path)
    // On error, serve stale if available
    if (entry) return entry.data as T
    throw err
  })

  _inflight.set(path, req as Promise<unknown>)
  return req
}

function revalidate(path: string): Promise<unknown> {
  if (_inflight.has(path)) return _inflight.get(path)!
  const req = request('GET', path).then((data) => {
    _cache.set(path, { data, ts: Date.now() })
    _inflight.delete(path)
    return data
  }).catch(() => { _inflight.delete(path) })
  _inflight.set(path, req)
  return req
}

/** Invalidate a cached path (e.g. after mutation) */
export function invalidateCache(path: string) {
  _cache.delete(path)
}

export const api = {
  get: <T>(path: string) => cachedGet<T>(path),
  getUncached: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
