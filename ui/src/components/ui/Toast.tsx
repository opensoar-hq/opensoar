/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: number
  type: ToastType
  title: string
  description?: string
}

interface ToastContextType {
  toast: (type: ToastType, title: string, description?: string) => void
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  warning: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

let toastId = 0

const ICONS: Record<ToastType, ReactNode> = {
  success: <CheckCircle size={16} className="text-success shrink-0" />,
  error: <XCircle size={16} className="text-danger shrink-0" />,
  warning: <AlertTriangle size={16} className="text-warning shrink-0" />,
  info: <Info size={16} className="text-info shrink-0" />,
}

const BORDER_COLORS: Record<ToastType, string> = {
  success: 'border-l-success',
  error: 'border-l-danger',
  warning: 'border-l-warning',
  info: 'border-l-info',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((type: ToastType, title: string, description?: string) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, type, title, description }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const ctx: ToastContextType = {
    toast: addToast,
    success: (title, desc) => addToast('success', title, desc),
    error: (title, desc) => addToast('error', title, desc),
    warning: (title, desc) => addToast('warning', title, desc),
    info: (title, desc) => addToast('info', title, desc),
  }

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 80, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              className={cn(
                'pointer-events-auto w-80 bg-surface border border-border rounded-lg shadow-xl',
                'border-l-[3px]',
                BORDER_COLORS[t.type],
              )}
            >
              <div className="flex items-start gap-3 px-4 py-3">
                {ICONS[t.type]}
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-heading">{t.title}</div>
                  {t.description && (
                    <div className="text-[11px] text-muted mt-0.5">{t.description}</div>
                  )}
                </div>
                <button
                  onClick={() => remove(t.id)}
                  className="p-0.5 text-muted hover:text-heading bg-transparent border-none cursor-pointer shrink-0"
                >
                  <X size={12} />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
