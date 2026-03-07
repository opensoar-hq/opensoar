import { motion } from 'framer-motion'
import { Check, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CheckboxProps {
  checked: boolean
  indeterminate?: boolean
  onChange: () => void
  className?: string
}

export function Checkbox({ checked, indeterminate, onChange, className }: CheckboxProps) {
  const isActive = checked || indeterminate

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? 'mixed' : checked}
      onClick={(e) => { e.stopPropagation(); onChange() }}
      className={cn(
        'relative w-4 h-4 rounded border-[1.5px] flex items-center justify-center',
        'cursor-pointer transition-all duration-150 bg-transparent p-0 shrink-0',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-1 focus-visible:ring-offset-bg',
        isActive
          ? 'border-accent bg-accent'
          : 'border-muted/50 hover:border-accent/60',
        className,
      )}
    >
      <motion.span
        initial={false}
        animate={{ scale: isActive ? 1 : 0, opacity: isActive ? 1 : 0 }}
        transition={{ type: 'spring', stiffness: 600, damping: 25 }}
        className="flex items-center justify-center"
      >
        {indeterminate
          ? <Minus size={10} strokeWidth={3} className="text-heading" />
          : <Check size={10} strokeWidth={3} className="text-heading" />
        }
      </motion.span>
    </button>
  )
}
