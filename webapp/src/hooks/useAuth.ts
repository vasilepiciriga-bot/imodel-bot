import { useEffect, useState } from 'react'
import { useAppStore } from '../store/appStore'
import { getMe } from '../api/session'

export function useAuth() {
  const setUser = useAppStore((s) => s.setUser)
  const user = useAppStore((s) => s.user)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getMe()
      .then((u) => {
        setUser(u)
        setLoading(false)
      })
      .catch((e) => {
        setError(e.message ?? 'Auth failed')
        setLoading(false)
      })
  }, [setUser])

  return { user, loading, error }
}
