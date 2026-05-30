import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export default function Card({ children, className = '', ...props }) {
  return (
    <div
      className={twMerge(
        clsx(
          'rounded-xl border border-zinc-700/50 bg-zinc-900/80 backdrop-blur-sm shadow-lg',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={twMerge(clsx('px-6 py-4 border-b border-zinc-700/50', className))}>
      {children}
    </div>
  )
}

export function CardContent({ children, className = '' }) {
  return (
    <div className={twMerge(clsx('px-6 py-4', className))}>
      {children}
    </div>
  )
}

export function CardTitle({ children, className = '' }) {
  return (
    <h3 className={twMerge(clsx('font-semibold text-zinc-100', className))}>
      {children}
    </h3>
  )
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={twMerge(clsx('px-6 py-4 border-t border-zinc-700/50', className))}>
      {children}
    </div>
  )
}
