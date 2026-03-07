import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

const inputBase = [
  'w-full px-3 py-2 text-sm rounded-md',
  'border border-border bg-bg text-heading',
  'placeholder:text-muted',
  'focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  'transition-colors',
].join(' ')

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, ...props }, ref) => {
    if (icon) {
      return (
        <div className="relative">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
            {icon}
          </span>
          <input
            ref={ref}
            className={cn(inputBase, 'pl-8', className)}
            {...props}
          />
        </div>
      )
    }
    return (
      <input
        ref={ref}
        className={cn(inputBase, className)}
        {...props}
      />
    )
  },
)
Input.displayName = 'Input'

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(inputBase, 'resize-none', className)}
        {...props}
      />
    )
  },
)
Textarea.displayName = 'Textarea'

export function Label({ children, className, ...props }: { children: ReactNode; className?: string; htmlFor?: string }) {
  return (
    <label className={cn('block text-xs font-medium text-muted mb-1.5', className)} {...props}>
      {children}
    </label>
  )
}
