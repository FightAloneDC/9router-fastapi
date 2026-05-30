import { useLocation, Link } from 'react-router-dom'
import { Menu, Search, LogOut, ChevronDown } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import { pageTitles } from '../constants/navigation'

export default function Header({ onMenuClick, title, description, icon: IconProp }) {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef(null)

  // Derive page info from route if not provided via props
  const pageInfo = pageTitles[location.pathname] || {
    title: '9Router',
    description: '',
    icon: null,
  }

  const resolvedTitle = title || pageInfo.title
  const resolvedDescription = description || pageInfo.description
  const ResolvedIcon = IconProp || pageInfo.icon

  // Close user menu on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <header className="h-16 border-b border-zinc-800 flex items-center justify-between px-4 lg:px-6 bg-zinc-900/50 backdrop-blur-sm">
      {/* Left side: mobile menu button + page title */}
      <div className="flex items-center gap-3">
        <button
          className="lg:hidden p-2 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors"
          onClick={onMenuClick}
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>

        <div className="flex items-center gap-3">
          {ResolvedIcon && (
            <div className="hidden sm:flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600/20">
              <ResolvedIcon size={16} className="text-blue-400" />
            </div>
          )}
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 leading-tight">
              {resolvedTitle}
            </h2>
            {resolvedDescription && (
              <p className="text-xs text-zinc-500 hidden sm:block leading-tight">
                {resolvedDescription}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Right side: search + user dropdown */}
      <div className="flex items-center gap-3">
        {/* Search placeholder */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/50 border border-zinc-700/50 text-zinc-500">
          <Search size={14} />
          <span className="text-xs">Search...</span>
        </div>

        {/* User dropdown */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-zinc-800 transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-xs font-medium text-white">
              {(user?.username || 'A').charAt(0).toUpperCase()}
            </div>
            <span className="hidden sm:block text-sm text-zinc-300">
              {user?.username || 'Admin'}
            </span>
            <ChevronDown size={14} className="text-zinc-500" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full mt-1 w-48 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-50 py-1">
              <div className="px-3 py-2 border-b border-zinc-800">
                <p className="text-sm font-medium text-zinc-200 truncate">
                  {user?.username || 'Admin'}
                </p>
                <p className="text-xs text-zinc-500">Administrator</p>
              </div>
              <button
                onClick={() => {
                  setUserMenuOpen(false)
                  logout()
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-zinc-400 hover:text-red-400 hover:bg-zinc-800/50 transition-colors"
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
