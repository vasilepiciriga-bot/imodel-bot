interface TelegramWebAppUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
  photo_url?: string
}

interface TelegramBackButton {
  isVisible: boolean
  show(): void
  hide(): void
  onClick(callback: () => void): void
  offClick(callback: () => void): void
}

interface TelegramWebApp {
  ready(): void
  expand(): void
  close(): void
  initData: string
  initDataUnsafe: {
    user?: TelegramWebAppUser
    start_param?: string
  }
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string>
  openInvoice(url: string, callback?: (status: string) => void): void
  openLink(url: string): void
  switchInlineQuery(query: string, choose_chat_types?: string[]): void
  HapticFeedback: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
    selectionChanged(): void
  }
  BackButton: TelegramBackButton
  addToHomeScreen?(): void
  checkHomeScreenStatus?(callback: (status: 'unsupported' | 'unknown' | 'added' | 'missed') => void): void
  downloadFile?(params: { url: string; file_name: string }): void
  shareToStory?(media_url: string, params?: { text?: string }): void
  disableVerticalSwipes?(): void
  enableClosingConfirmation?(): void
  onEvent?(eventType: string, eventHandler: () => void): void
  offEvent?(eventType: string, eventHandler: () => void): void
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp
  }
}
