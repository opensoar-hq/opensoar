import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

const ease = [0.25, 0.1, 0.25, 1] as [number, number, number, number]

export function Drawer({ open, onClose, title, wide, children }: {
  open: boolean
  onClose: () => void
  title: string
  wide?: boolean
  children: React.ReactNode
}) {
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
        <div className="fixed inset-0 z-50 flex justify-end">
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.div
            className={cn(
              'relative w-full bg-surface border-l border-border flex flex-col',
              wide ? 'max-w-3xl' : 'max-w-2xl',
            )}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.3, ease }}
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
              <h2 className="text-sm font-semibold text-heading m-0">{title}</h2>
              <button
                onClick={onClose}
                className="p-1.5 rounded-md text-muted hover:text-heading hover:bg-surface-hover bg-transparent border-none cursor-pointer transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-5">
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
