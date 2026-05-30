import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export default function Input({
  label,
  error,
  hint,
  className = '',
  ...props
}) {
  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-zinc-300 mb-1.5">
          {label}
        </label>
      )}
      <input
        className={twMerge(
          clsx(
            'w-full rounded-lg border bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            error
              ? 'border-red-500/50 focus:ring-red-500'
              : 'border-zinc-700 hover:border-zinc-600',
            className
          )
        )}
        {...props}
      />
      {error ? (
        <p className="mt-1.5 text-sm text-red-400">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-zinc-500">{hint}</p>
      ) : null}
    </div>
  )
}
