import { useEffect, useRef, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

const ease = [0.25, 0.1, 0.25, 1] as [number, number, number, number]

interface DialogProps {
  open: boolean
  onClose: () => void
  children: ReactNode
}

export function Dialog({ open, onClose, children }: DialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div
          ref={overlayRef}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
        >
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          />
          <motion.div
            className="relative w-full max-w-lg"
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 4 }}
            transition={{ duration: 0.2, ease }}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export function DialogContent({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('bg-surface border border-border rounded-lg shadow-2xl', className)}>
      {children}
    </div>
  )
}

export function DialogHeader({ children, onClose, className }: { children: ReactNode; onClose?: () => void; className?: string }) {
  return (
    <div className={cn('flex items-center justify-between px-5 py-4 border-b border-border', className)}>
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          className="p-1.5 -mr-1.5 rounded-md text-muted hover:text-heading hover:bg-surface-hover bg-transparent border-none cursor-pointer transition-colors"
        >
          <X size={16} />
        </button>
      )}
    </div>
  )
}

export function DialogTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn('text-sm font-semibold text-heading m-0', className)}>{children}</h2>
}

export function DialogBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('px-5 py-4', className)}>{children}</div>
}

export function DialogFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-center justify-end gap-2 px-5 py-3 border-t border-border', className)}>
      {children}
    </div>
  )
}
