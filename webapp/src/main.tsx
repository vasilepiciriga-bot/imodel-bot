// tg.ready() must be the absolute first thing — before React mounts
const tg = window.Telegram?.WebApp
tg?.ready()
tg?.expand()

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
