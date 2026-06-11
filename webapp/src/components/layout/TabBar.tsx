import { motion } from 'framer-motion'
import { Sparkles, Palette, Images, ShoppingBag, User, Settings } from 'lucide-react'
import { useAppStore } from '../../store/appStore'

const tg = window.Telegram?.WebApp

const TABS = [
  { id: 'studio',  icon: Sparkles,     label: 'Studio' },
  { id: 'styles',  icon: Palette,      label: 'Styles' },
  { id: 'gallery', icon: Images,       label: 'Gallery' },
  { id: 'shop',    icon: ShoppingBag,  label: 'Shop' },
  { id: 'profile', icon: User,         label: 'Me' },
] as const

const ADMIN_ROLES = new Set(['owner', 'admin', 'operator', 'support'])

export function TabBar() {
  const tab    = useAppStore((s) => s.tab)
  const setTab = useAppStore((s) => s.setTab)
  const user   = useAppStore((s) => s.user)
  const isAdmin = user?.role && ADMIN_ROLES.has(user.role)

  return (
    <nav
      className="flex items-end pb-safe bg-white/80 shadow-tab border-t border-black/[0.06]"
      style={{ backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}
    >
      {TABS.map(({ id, icon: Icon, label }) => {
        const active = tab === id
        return (
          <button
            key={id}
            onClick={() => {
              tg?.HapticFeedback?.selectionChanged()
              setTab(id)
            }}
            className="flex-1 flex flex-col items-center gap-0.5 pt-2 pb-1 relative"
          >
            {active && (
              <motion.div
                layoutId="tab-indicator"
                className="absolute inset-0 bg-gradient-to-b from-[#6C47FF]/10 to-transparent rounded-t-xl"
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              />
            )}
            <motion.div animate={{ scale: active ? 1.1 : 1 }} transition={{ type: 'spring', stiffness: 400, damping: 25 }}>
              <Icon
                size={22}
                strokeWidth={active ? 2.2 : 1.6}
                className={active ? 'text-[#6C47FF]' : 'text-[#6E6E73]'}
              />
            </motion.div>
            <span className={`text-[10px] font-medium ${active ? 'text-[#6C47FF]' : 'text-[#6E6E73]'}`}>
              {label}
            </span>
          </button>
        )
      })}

      {isAdmin && (
        <button
          onClick={() => {
            tg?.HapticFeedback?.selectionChanged()
            setTab('admin' as Parameters<typeof setTab>[0])
          }}
          className="flex-1 flex flex-col items-center gap-0.5 pt-2 pb-1 relative"
        >
          {tab === 'admin' && (
            <motion.div
              layoutId="tab-indicator"
              className="absolute inset-0 bg-gradient-to-b from-[#FF3B30]/10 to-transparent rounded-t-xl"
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
          )}
          <motion.div animate={{ scale: tab === 'admin' ? 1.1 : 1 }} transition={{ type: 'spring', stiffness: 400, damping: 25 }}>
            <Settings
              size={22}
              strokeWidth={tab === 'admin' ? 2.2 : 1.6}
              className={tab === 'admin' ? 'text-[#FF3B30]' : 'text-[#6E6E73]'}
            />
          </motion.div>
          <span className={`text-[10px] font-medium ${tab === 'admin' ? 'text-[#FF3B30]' : 'text-[#6E6E73]'}`}>
            Admin
          </span>
        </button>
      )}
    </nav>
  )
}
