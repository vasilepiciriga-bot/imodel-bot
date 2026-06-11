import { Suspense, lazy, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { TabBar } from './components/layout/TabBar'
import { ScreenSkeleton } from './components/shared/ScreenSkeleton'
import { OnboardingOverlay, useOnboarding } from './components/shared/OnboardingOverlay'
import { ToastProvider } from './components/shared/Toast'
import { useAuth } from './hooks/useAuth'
import { useAppStore } from './store/appStore'
import { track } from './api/analytics'

const Studio  = lazy(() => import('./screens/Studio'))
const Styles  = lazy(() => import('./screens/Styles'))
const Gallery = lazy(() => import('./screens/Gallery'))
const Shop    = lazy(() => import('./screens/Shop'))
const Profile = lazy(() => import('./screens/Profile'))
const Admin   = lazy(() => import('./screens/Admin'))

const SCREENS = { studio: Studio, styles: Styles, gallery: Gallery, shop: Shop, profile: Profile, admin: Admin }

function AuthGate({ children }: { children: React.ReactNode }) {
  const { loading, error } = useAuth()

  if (loading) {
    return (
      <div className="flex flex-col h-screen bg-[#F5F5F7]">
        <ScreenSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col h-screen items-center justify-center gap-4 p-8 text-center bg-[#F5F5F7]">
        <span className="text-4xl">⚠️</span>
        <p className="text-[16px] font-semibold text-[#1D1D1F]">Could not authenticate</p>
        <p className="text-[13px] text-[#6E6E73]">Please open this app from Telegram</p>
      </div>
    )
  }

  return <>{children}</>
}

export default function App() {
  const tab = useAppStore((s) => s.tab)
  const Screen = SCREENS[tab as keyof typeof SCREENS] ?? SCREENS.studio
  const needsOnboarding = useOnboarding()
  const [showOnboarding, setShowOnboarding] = useState(needsOnboarding)

  useEffect(() => { track('tab_viewed', { tab }) }, [tab])
  useEffect(() => {
    if (needsOnboarding) track('onboarding_viewed', { source: 'webapp' })
  }, [needsOnboarding])

  return (
    <ToastProvider>
    <AuthGate>
      <AnimatePresence>
        {showOnboarding && (
          <OnboardingOverlay onDone={() => setShowOnboarding(false)} />
        )}
      </AnimatePresence>
      <div
        className="flex flex-col h-dvh bg-[#F5F5F7] overflow-hidden"
        style={{
          maxWidth: 480,
          margin: '0 auto',
          paddingTop: 'var(--tg-safe-top, env(safe-area-inset-top, 0px))',
        }}
      >
        <div className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="h-full"
            >
              <Suspense fallback={<ScreenSkeleton />}>
                <Screen />
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </div>
        <TabBar />
      </div>
    </AuthGate>
    </ToastProvider>
  )
}
