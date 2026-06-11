import { useContext } from 'react'
import { ToastContext, type ToastOptions } from '../components/shared/Toast'

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export type { ToastOptions }
