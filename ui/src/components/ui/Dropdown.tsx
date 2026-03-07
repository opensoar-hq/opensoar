import { useState, useRef, useEffect, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'

interface DropdownProps {
  trigger: ReactNode
  children: ReactNode
  align?: 'left' | 'right'
  className?: string
}

export function Dropdown({ trigger, children, align = 'left', className }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div ref={ref} className="relative inline-flex">
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.12, ease: [0.25, 0.1, 0.25, 1] }}
            className={cn(
              'absolute z-50 top-full mt-1 min-w-[180px]',
              'bg-surface border border-border rounded-lg shadow-xl',
              'py-1',
              align === 'right' ? 'right-0' : 'left-0',
              className,
            )}
            onClick={() => setOpen(false)}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function DropdownItem({
  children,
  onClick,
  variant = 'default',
  disabled,
  className,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'default' | 'danger'
  disabled?: boolean
  className?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'w-full text-left px-3 py-1.5 text-xs flex items-center gap-2',
        'bg-transparent border-none cursor-pointer transition-colors',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'danger'
          ? 'text-danger hover:bg-danger/10'
          : 'text-heading hover:bg-surface-hover',
        className,
      )}
    >
      {children}
    </button>
  )
}

export function DropdownSeparator() {
  return <div className="my-1 border-t border-border" />
}
