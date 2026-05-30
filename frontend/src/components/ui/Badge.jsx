import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

const variants = {
  default: 'bg-zinc-700 text-zinc-200',
  primary: 'bg-primary-600/20 text-primary-400 border border-primary-500/30',
  success: 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30',
  warning: 'bg-amber-600/20 text-amber-400 border border-amber-500/30',
  danger: 'bg-red-600/20 text-red-400 border border-red-500/30',
  info: 'bg-sky-600/20 text-sky-400 border border-sky-500/30',
}

const sizes = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
}

export default function Badge({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  dot = false,
  ...props
}) {
  return (
    <span
      className={twMerge(
        clsx(
          'inline-flex items-center rounded-full font-medium',
          variants[variant],
          sizes[size],
          dot && 'relative pl-5 before:absolute before:left-2 before:top-1/2 before:-translate-y-1/2 before:h-1.5 before:w-1.5 before:rounded-full before:bg-current',
          className
        )
      )}
      {...props}
    >
      {children}
    </span>
  )
}
