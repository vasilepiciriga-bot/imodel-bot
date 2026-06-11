interface TelegramWebAppUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
  photo_url?: string
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
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp
  }
}
