import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const variants = {
  default: 'bg-surface border-border text-heading hover:bg-surface-hover',
  primary: 'bg-accent/15 border-accent/30 text-accent hover:bg-accent/25',
  danger: 'bg-danger/15 border-danger/30 text-danger hover:bg-danger/25',
  ghost: 'bg-transparent border-transparent text-text hover:bg-surface-hover hover:text-heading',
  success: 'bg-success/15 border-success/30 text-success hover:bg-success/25',
}

const sizes = {
  sm: 'px-2.5 py-1 text-xs gap-1',
  md: 'px-3 py-1.5 text-sm gap-1.5',
  lg: 'px-4 py-2 text-sm gap-2',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants
  size?: keyof typeof sizes
}

export function Button({ variant = 'default', size = 'md', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md border font-medium cursor-pointer',
        'transition-all duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
        'active:scale-[0.98]',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  )
}
