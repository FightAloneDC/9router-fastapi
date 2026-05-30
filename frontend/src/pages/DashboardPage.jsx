import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import { Wifi, Server, Activity, ChevronRight } from 'lucide-react'
import { navItems, systemItems, debugItems, settingsItem } from '../constants/navigation'

const statCards = [
  {
    label: 'Endpoints',
    value: '--',
    icon: Wifi,
    color: 'primary',
    bgClass: 'bg-blue-600/20',
    textClass: 'text-blue-400',
  },
  {
    label: 'Providers',
    value: '--',
    icon: Server,
    color: 'emerald',
    bgClass: 'bg-emerald-600/20',
    textClass: 'text-emerald-400',
  },
  {
    label: 'Usage',
    value: '--',
    icon: Activity,
    color: 'sky',
    bgClass: 'bg-sky-600/20',
    textClass: 'text-sky-400',
  },
]

// Build navigation cards from constants (skip Dashboard itself at index 0)
const navCards = navItems.slice(1).map((item) => ({
  label: item.label,
  desc: item.description,
  path: item.path,
  icon: item.icon,
}))

// Add system and debug items to the cards grid
const extraCards = [
  ...systemItems.map((item) => ({
    label: item.label,
    desc: item.description,
    path: item.path,
    icon: item.icon,
  })),
  ...debugItems.map((item) => ({
    label: item.label,
    desc: item.description,
    path: item.path,
    icon: item.icon,
  })),
  {
    label: settingsItem.label,
    desc: settingsItem.description,
    path: settingsItem.path,
    icon: settingsItem.icon,
  },
]

const allNavCards = [...navCards, ...extraCards]

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user)

  return (
    <div className="space-y-6">
      {/* Welcome header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">
          Welcome to 9Router
        </h1>
        <p className="mt-1 text-zinc-400">
          {user
            ? `Logged in as ${user.username}`
            : 'Network management and monitoring dashboard'}
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <Card key={card.label}>
              <CardContent className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${card.bgClass}`}>
                  <Icon size={20} className={card.textClass} />
                </div>
                <div>
                  <p className="text-sm text-zinc-400">{card.label}</p>
                  <p className="text-2xl font-bold text-zinc-100">{card.value}</p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Quick Links + System Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Quick Links */}
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-zinc-100">Quick Links</h3>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {navItems.slice(1, 5).map((item) => {
                const Icon = item.icon
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-zinc-800 transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center">
                        <Icon size={14} className="text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-zinc-200 group-hover:text-blue-400 transition-colors">
                          {item.label}
                        </p>
                        <p className="text-xs text-zinc-500">{item.description}</p>
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-zinc-600 group-hover:text-zinc-400" />
                  </Link>
                )
              })}
            </div>
          </CardContent>
        </Card>

        {/* System Status */}
        <Card>
          <CardHeader>
            <h3 className="text-lg font-semibold text-zinc-100">System Status</h3>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">API Server</span>
                <Badge variant="success">Online</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Database</span>
                <Badge variant="success">Connected</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-zinc-400">Authentication</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="pt-2 border-t border-zinc-800">
                <p className="text-xs text-zinc-500">All systems operational</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Navigation cards grid - all sections */}
      <div>
        <h3 className="text-lg font-semibold text-zinc-100 mb-4">All Sections</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {allNavCards.map((item) => {
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                className="group flex items-center gap-3 p-4 rounded-lg border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 hover:border-zinc-700 transition-all duration-150"
              >
                <div className="w-9 h-9 rounded-lg bg-blue-600/20 flex items-center justify-center shrink-0">
                  <Icon size={16} className="text-blue-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-200 group-hover:text-blue-400 transition-colors truncate">
                    {item.label}
                  </p>
                  <p className="text-[11px] text-zinc-500 truncate">
                    {item.desc}
                  </p>
                </div>
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
