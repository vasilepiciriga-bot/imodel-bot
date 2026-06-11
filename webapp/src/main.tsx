// tg.ready() must be the absolute first thing — before React mounts
const tg = window.Telegram?.WebApp
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _tg = tg as any
_tg?.ready()
_tg?.expand()
_tg?.disableVerticalSwipes?.()
_tg?.enableClosingConfirmation?.()

// Sync Telegram safe-area insets as CSS variables so App.tsx can use them.
// safeAreaInset (Bot API 7.8): OS-level insets — status bar, Dynamic Island
// contentSafeAreaInset (Bot API 8.0): Telegram header bar (the "× Close" strip)
// Sum both: the expanded WebView extends behind both layers on iOS.
function _syncSafeAreas() {
  const sa  = _tg?.safeAreaInset        as { top?: number; bottom?: number } | undefined
  const cas = _tg?.contentSafeAreaInset as { top?: number; bottom?: number } | undefined
  const top    = (sa?.top    ?? 0) + (cas?.top    ?? 0)
  const bottom = (sa?.bottom ?? 0) + (cas?.bottom ?? 0)
  const root = document.documentElement
  // Only set when non-zero: when 0, leave the var unset so the CSS
  // env(safe-area-inset-*) fallback in App.tsx can supply the OS value.
  if (top    > 0) root.style.setProperty('--tg-safe-top',    `${top}px`)
  if (bottom > 0) root.style.setProperty('--tg-safe-bottom', `${bottom}px`)
}
_syncSafeAreas()
_tg?.onEvent?.('safeAreaChanged',        _syncSafeAreas)
_tg?.onEvent?.('contentSafeAreaChanged', _syncSafeAreas)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
