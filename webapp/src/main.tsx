// tg.ready() must be the absolute first thing — before React mounts
const tg = window.Telegram?.WebApp
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _tg = tg as any
_tg?.ready()
_tg?.expand()
_tg?.disableVerticalSwipes?.()
_tg?.enableClosingConfirmation?.()

// Sync Telegram safe-area insets as CSS variables so App.tsx can use them.
// contentSafeAreaInsets accounts for Telegram's own header; safeAreaInsets is the
// raw OS notch/home-indicator. We take the max so whichever is larger wins.
function _syncSafeAreas() {
  const cas = _tg?.contentSafeAreaInsets as { top?: number; bottom?: number } | undefined
  const sa  = _tg?.safeAreaInsets        as { top?: number; bottom?: number } | undefined
  const top    = Math.max(cas?.top    ?? 0, sa?.top    ?? 0)
  const bottom = Math.max(cas?.bottom ?? 0, sa?.bottom ?? 0)
  const root = document.documentElement
  root.style.setProperty('--tg-safe-top',    `${top}px`)
  root.style.setProperty('--tg-safe-bottom', `${bottom}px`)
}
_syncSafeAreas()
_tg?.onEvent?.('safe_area_changed',         _syncSafeAreas)
_tg?.onEvent?.('content_safe_area_changed', _syncSafeAreas)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
