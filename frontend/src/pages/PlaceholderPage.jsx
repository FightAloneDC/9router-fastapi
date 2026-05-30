import { useLocation } from 'react-router-dom'
import { Construction } from 'lucide-react'
import { pageTitles } from '../constants/navigation'

export default function PlaceholderPage() {
  const location = useLocation()
  const pageInfo = pageTitles[location.pathname]
  const Icon = pageInfo?.icon || Construction

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      {/* Icon */}
      <div className="w-16 h-16 rounded-2xl bg-blue-600/20 flex items-center justify-center mb-6">
        <Icon size={28} className="text-blue-400" />
      </div>

      {/* Title */}
      <h1 className="text-2xl font-bold text-zinc-100 mb-2">
        {pageInfo?.title || 'Page'}
      </h1>

      {/* Description */}
      {pageInfo?.description && (
        <p className="text-zinc-400 mb-6 max-w-md">
          {pageInfo.description}
        </p>
      )}

      {/* Coming soon badge */}
      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-900 border border-zinc-800">
        <Construction size={16} className="text-amber-400" />
        <span className="text-sm text-zinc-300">Coming soon</span>
      </div>
    </div>
  )
}
