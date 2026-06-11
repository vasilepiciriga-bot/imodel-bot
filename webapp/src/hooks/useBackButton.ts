import { useEffect } from 'react'

const tg = window.Telegram?.WebApp

/**
 * Show Telegram's BackButton while the component is mounted and call onClose
 * when the user taps it. Hides the button on unmount.
 *
 * Use this in every overlay / modal so Android hardware back / Telegram back
 * button dismisses the overlay instead of closing the whole Mini App.
 */
export function useBackButton(onClose: () => void) {
  useEffect(() => {
    if (!tg?.BackButton) return
    tg.BackButton.show()
    tg.BackButton.onClick(onClose)
    return () => {
      tg.BackButton.offClick(onClose)
      tg.BackButton.hide()
    }
  }, [onClose])
}
