import { Link, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import {
  X,
  ChevronDown,
  ChevronRight,
  LogOut,
} from 'lucide-react'
import { useState, useCallback, useRef, useEffect } from 'react'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { navItems, systemItems, debugItems, settingsItem } from '../../constants/navigation'
import Header from '../Header'

/**
 * Sidebar navigation link component
 */
function NavLink({ item, isActive, onClick }) {
  const Icon = item.icon
  return (
    <Link
      to={item.path}
      onClick={onClick}
      className={twMerge(
        clsx(
          'flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150',
          isActive
            ? 'bg-blue-600/20 text-blue-400'
            : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
        )
      )}
    >
      <Icon size={16} className={isActive ? 'text-blue-400' : 'text-zinc-500'} />
      <span>{item.label}</span>
    </Link>
  )
}

/**
 * Section label for sidebar groups
 */
function SectionLabel({ children }) {
  return (
    <div className="px-3 pt-5 pb-2">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        {children}
      </span>
    </div>
  )
}

/**
 * Media Providers accordion with sub-items
 */
function MediaProvidersAccordion({ isOpen, onToggle, subItems, pathname, closeMobile }) {
  const Icon = systemItems[0].icon
  const isParentActive = pathname.startsWith('/media-providers')

  return (
    <div>
      {/* Accordion toggle button */}
      <button
        onClick={onToggle}
        className={twMerge(
          clsx(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150',
            isParentActive && !isOpen
              ? 'bg-blue-600/20 text-blue-400'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
          )
        )}
      >
        <Icon size={16} className={isParentActive ? 'text-blue-400' : 'text-zinc-500'} />
        <span className="flex-1 text-left">Media Providers</span>
        {isOpen ? (
          <ChevronDown size={14} className="text-zinc-500" />
        ) : (
          <ChevronRight size={14} className="text-zinc-500" />
        )}
      </button>

      {/* Sub-items */}
      {isOpen && (
        <div className="ml-3 pl-3 border-l border-zinc-800 mt-1 space-y-0.5">
          {subItems.map((sub) => {
            const SubIcon = sub.icon
            const isSubActive = (
              pathname === sub.path
              || pathname.startsWith(`${sub.path}/`)
            )
            return (
              <Link
                key={sub.path}
                to={sub.path}
                onClick={closeMobile}
                className={twMerge(
                  clsx(
                    'flex items-center gap-3 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-150',
                    isSubActive
                      ? 'bg-blue-600/20 text-blue-400'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
                  )
                )}
              >
                <SubIcon size={14} className={isSubActive ? 'text-blue-400' : 'text-zinc-500'} />
                <span>{sub.label}</span>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * Settings accordion with sub-items
 */
function SettingsAccordion({ isOpen, onToggle, subItems, pathname, closeMobile }) {
  const Icon = settingsItem.icon
  const isParentActive = pathname.startsWith('/settings')

  return (
    <div>
      <button
        onClick={onToggle}
        className={twMerge(
          clsx(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-150',
            isParentActive && !isOpen
              ? 'bg-blue-600/20 text-blue-400'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50',
          ),
        )}
      >
        <Icon
          size={16}
          className={isParentActive ? 'text-blue-400' : 'text-zinc-500'}
        />
        <span className="flex-1 text-left">Settings</span>
        {isOpen ? (
          <ChevronDown size={14} className="text-zinc-500" />
        ) : (
          <ChevronRight size={14} className="text-zinc-500" />
        )}
      </button>

      {isOpen && (
        <div className="ml-3 pl-3 border-l border-zinc-800 mt-1 space-y-0.5">
          {subItems.map((sub) => {
            const SubIcon = sub.icon
            const isSubActive = pathname === sub.path
            return (
              <Link
                key={sub.path}
                to={sub.path}
                onClick={closeMobile}
                className={twMerge(
                  clsx(
                    'flex items-center gap-3 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-150',
                    isSubActive
                      ? 'bg-blue-600/20 text-blue-400'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50',
                  ),
                )}
              >
                <SubIcon
                  size={14}
                  className={isSubActive ? 'text-blue-400' : 'text-zinc-500'}
                />
                <span>{sub.label}</span>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * Full sidebar content (shared between desktop and mobile)
 */
function SidebarContent({ pathname, closeMobile, user, logout }) {
  const [mediaAccordionOpen, setMediaAccordionOpen] = useState(
    pathname.startsWith('/media-providers'),
  )
  const [settingsAccordionOpen, setSettingsAccordionOpen] = useState(
    pathname.startsWith('/settings'),
  )

  useEffect(() => {
    if (pathname.startsWith('/settings')) {
      setSettingsAccordionOpen(true)
    }
  }, [pathname])

  const isActive = useCallback(
    (path) => {
      if (path === '/') return pathname === '/'
      return pathname === path || pathname.startsWith(path + '/')
    },
    [pathname]
  )

  return (
    <div className="flex flex-col h-full">
      {/* Traffic lights + Logo */}
      <div className="flex items-center justify-between h-14 px-4 border-b border-zinc-800">
        <Link
          to="/"
          onClick={closeMobile}
          className="flex items-center gap-2.5"
        >
          {/* Traffic light dots */}
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <div className="w-3 h-3 rounded-full bg-green-500" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-[15px] font-bold text-white">9Router</span>
            <span className="text-[11px] text-zinc-500">v0.1.0</span>
          </div>
        </Link>
        {/* Mobile close button */}
        <button
          className="lg:hidden p-1 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors"
          onClick={closeMobile}
        >
          <X size={18} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-2">
        {/* Main nav items */}
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            item={item}
            isActive={isActive(item.path)}
            onClick={closeMobile}
          />
        ))}

        {/* System section */}
        <SectionLabel>System</SectionLabel>

        {/* Media Providers accordion */}
        <MediaProvidersAccordion
          isOpen={mediaAccordionOpen}
          onToggle={() => setMediaAccordionOpen(!mediaAccordionOpen)}
          subItems={systemItems[0].children}
          pathname={pathname}
          closeMobile={closeMobile}
        />

        {/* Other system items */}
        {systemItems.slice(1).map((item) => (
          <NavLink
            key={item.path}
            item={item}
            isActive={isActive(item.path)}
            onClick={closeMobile}
          />
        ))}

        {/* Debug section */}
        <SectionLabel>Debug</SectionLabel>

        {debugItems.map((item) => (
          <NavLink
            key={item.path}
            item={item}
            isActive={isActive(item.path)}
            onClick={closeMobile}
          />
        ))}

        <SectionLabel>Settings</SectionLabel>

        <SettingsAccordion
          isOpen={settingsAccordionOpen}
          onToggle={() => setSettingsAccordionOpen(!settingsAccordionOpen)}
          subItems={settingsItem.children}
          pathname={pathname}
          closeMobile={closeMobile}
        />
      </nav>

      {/* User footer */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-medium text-white">
            {(user?.username || 'A').charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-zinc-200 truncate">
              {user?.username || 'Admin'}
            </p>
            <p className="text-[11px] text-zinc-500">Administrator</p>
          </div>
        </div>
        <button
          onClick={() => {
            closeMobile()
            logout()
          }}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] font-medium text-zinc-400 hover:text-red-400 hover:bg-zinc-800/50 transition-colors"
        >
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </div>
  )
}

/**
 * DashboardLayout - Main layout with sidebar + header for all dashboard pages
 */
export default function DashboardLayout({ children }) {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const closeMobile = useCallback(() => setSidebarOpen(false), [])

  return (
    <div className="min-h-screen bg-zinc-950 flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-sm"
          onClick={closeMobile}
        />
      )}

      {/* Sidebar - Desktop */}
      <aside className="hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:w-64 bg-zinc-900 border-r border-zinc-800">
        <SidebarContent
          pathname={location.pathname}
          closeMobile={closeMobile}
          user={user}
          logout={logout}
        />
      </aside>

      {/* Sidebar - Mobile (slide-out) */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-zinc-900 border-r border-zinc-800 transform transition-transform duration-300 ease-in-out lg:hidden',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <SidebarContent
          pathname={location.pathname}
          closeMobile={closeMobile}
          user={user}
          logout={logout}
        />
      </aside>

      {/* Main content */}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        {/* Header */}
        <Header onMenuClick={() => setSidebarOpen(true)} />

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
