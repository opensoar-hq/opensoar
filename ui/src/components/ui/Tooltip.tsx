import { useState, useRef, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface TooltipProps {
  content: string
  children: ReactNode
  side?: 'top' | 'bottom'
  className?: string
}

export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  const show = () => {
    clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => setVisible(true), 300)
  }

  const hide = () => {
    clearTimeout(timeoutRef.current)
    setVisible(false)
  }

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible && (
        <span
          className={cn(
            'absolute left-1/2 -translate-x-1/2 z-50 pointer-events-none',
            'px-2 py-1 text-[11px] font-medium text-heading whitespace-nowrap',
            'bg-overlay border border-border rounded-md shadow-lg',
            side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
