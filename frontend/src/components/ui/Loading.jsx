import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export default function Loading({ size = 'md', className = '' }) {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  }

  return (
    <div className={twMerge(clsx('flex items-center justify-center', className))}>
      <div
        className={clsx(
          'animate-spin rounded-full border-2 border-zinc-600 border-t-primary-500',
          sizes[size]
        )}
      />
    </div>
  )
}

export function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-950">
      <Loading size="lg" />
    </div>
  )
}
