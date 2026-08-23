import {
  LayoutDashboard,
  Server,
  BarChart3,
  Database,
  Shield,
  Terminal,
  Binary,
  Volume2,
  Mic,
  Search,
  Globe,
  Image,
  Eye,
  Video,
  Music,
  Network,
  Puzzle,
  Combine,
  Monitor,
  Settings,
  MessageSquare,
} from 'lucide-react'
import { settingsNavItems } from './settingsNavigation'

// Main navigation items
export const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard, description: 'Overview and quick access' },
  { path: '/endpoints', label: 'Endpoints', icon: Globe, description: 'Manage API endpoints and routing' },
  { path: '/providers', label: 'LLM Providers', icon: Server, description: 'Chat/LLM providers, API keys, and models' },
  { path: '/chat', label: 'Chat', icon: MessageSquare, description: 'Test providers with chat interface' },
  { path: '/usage', label: 'Usage', icon: BarChart3, description: 'API usage statistics and analytics' },
  { path: '/quota-tracker', label: 'Quota Tracker', icon: Database, description: 'Track and manage API quotas' },
  { path: '/mitm', label: 'MITM', icon: Shield, description: 'Man-in-the-middle proxy inspection' },
  { path: '/cli-tools', label: 'CLI Tools', icon: Terminal, description: 'Command-line utilities and tools' },
]

// Media provider sub-items (for sidebar accordion)
export const mediaProviderKinds = [
  { path: '/media-providers/embedding', label: 'Embedding', icon: Binary, description: 'Text embedding models' },
  { path: '/media-providers/tts', label: 'Text to Speech', icon: Volume2, description: 'Text-to-speech providers' },
  { path: '/media-providers/stt', label: 'Speech to Text', icon: Mic, description: 'Speech-to-text providers' },
  { path: '/media-providers/webSearch', label: 'Web', icon: Search, description: 'Web search & fetch providers' },
  { path: '/media-providers/image', label: 'Images', icon: Image, description: 'Image generation providers' },
]

// System section items
export const systemItems = [
  {
    path: '/media-providers',
    label: 'Media Providers',
    icon: Image,
    description: 'Configure media processing providers',
    hasChildren: true,
    children: mediaProviderKinds,
  },
  { path: '/combos', label: 'Combos', icon: Combine, description: 'Manage provider combos and routing strategies' },
  { path: '/proxy-pools', label: 'Proxy Pools', icon: Network, description: 'Manage proxy pool configurations' },
  { path: '/skills', label: 'Skills', icon: Puzzle, description: 'Manage agent skills and capabilities' },
]

// Debug section items
export const debugItems = [
  { path: '/console-log', label: 'Console Log', icon: Monitor, description: 'View system logs and debug output' },
]

// Settings accordion (sidebar submenu)
export const settingsItem = {
  path: '/settings',
  label: 'Settings',
  icon: Settings,
  description: 'Application configuration and preferences',
  hasChildren: true,
  children: settingsNavItems,
}

// Page title/description/icon mapping by route path
export const pageTitles = {
  '/': { title: 'Dashboard', description: 'Overview and quick access', icon: LayoutDashboard },
  '/endpoints': { title: 'Endpoints', description: 'Manage API endpoints and routing', icon: Globe },
  '/providers': { title: 'LLM Providers', description: 'Chat/LLM providers, API keys, and models', icon: Server },
  '/chat': { title: 'Chat', description: 'Test providers with chat interface', icon: MessageSquare },
  '/usage': { title: 'Usage & Analytics', description: 'Monitor your API usage, token consumption, and request logs', icon: BarChart3 },
  '/quota-tracker': { title: 'Quota Tracker', description: 'Track and manage API quotas', icon: Database },
  '/mitm': { title: 'MITM', description: 'Man-in-the-middle proxy inspection', icon: Shield },
  '/cli-tools': { title: 'CLI Tools', description: 'Command-line utilities and tools', icon: Terminal },
  '/media-providers': { title: 'Media Providers', description: 'Configure media processing providers', icon: Image },
  '/media-providers/embedding': { title: 'Embedding', description: 'Text embedding models', icon: Binary },
  '/media-providers/tts': { title: 'Text to Speech', description: 'Text-to-speech providers', icon: Volume2 },
  '/media-providers/stt': { title: 'Speech to Text', description: 'Speech-to-text providers', icon: Mic },
  '/media-providers/webSearch': { title: 'Web', description: 'Web search & fetch providers', icon: Search },
  '/media-providers/image': { title: 'Images', description: 'Image generation providers', icon: Image },
  '/combos': { title: 'Combos', description: 'Manage provider combos and routing strategies', icon: Combine },
  '/proxy-pools': { title: 'Proxy Pools', description: 'Manage proxy pool configurations', icon: Network },
  '/skills': { title: 'Skills', description: 'Manage agent skills and capabilities', icon: Puzzle },
  '/console-log': { title: 'Console Log', description: 'View system logs and debug output', icon: Monitor },
  '/settings': { title: 'Settings', description: 'Application configuration', icon: Settings },
  ...Object.fromEntries(
    settingsNavItems.map((item) => [
      item.path,
      {
        title: item.label,
        description: item.description,
        icon: item.icon,
      },
    ]),
  ),
}
