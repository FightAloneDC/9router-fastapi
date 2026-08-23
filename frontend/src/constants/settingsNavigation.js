import {
  Monitor,
  Shield,
  Database,
  GitBranch,
  Activity,
  Globe,
  Zap,
} from 'lucide-react'

export const settingsNavItems = [
  {
    path: '/settings/general',
    label: 'General',
    icon: Monitor,
    description: 'Theme, shutdown, and session',
  },
  {
    path: '/settings/security',
    label: 'Security',
    icon: Shield,
    description: 'Password and OIDC authentication',
  },
  {
    path: '/settings/backup',
    label: 'Backup & Migration',
    icon: Database,
    description: 'Export and restore application data',
  },
  {
    path: '/settings/routing',
    label: 'Routing',
    icon: GitBranch,
    description: 'Combo and provider routing strategies',
  },
  {
    path: '/settings/observability',
    label: 'Observability',
    icon: Activity,
    description: 'Usage logging and retention',
  },
  {
    path: '/settings/network',
    label: 'Network',
    icon: Globe,
    description: 'Cloud tunnel, Tailscale, and DNS',
  },
  {
    path: '/settings/experimental',
    label: 'Experimental',
    icon: Zap,
    description: 'RTK, Caveman mode, and DNS tools',
  },
]
