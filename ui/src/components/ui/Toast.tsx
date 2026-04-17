/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface ToastOptions {
  action?: ToastAction
  /** Override auto-dismiss in ms. 0 or negative keeps the toast until dismissed. */
  duration?: number
}

interface ToastEntry {
  id: number
  type: ToastType
  title: string
  description?: string
  action?: ToastAction
  duration: number
}

interface ToastContextType {
  toast: (type: ToastType, title: string, description?: string, options?: ToastOptions) => number
  success: (title: string, description?: string, options?: ToastOptions) => number
  error: (title: string, description?: string, options?: ToastOptions) => number
  warning: (title: string, description?: string, options?: ToastOptions) => number
  info: (title: string, description?: string, options?: ToastOptions) => number
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

let toastId = 0

const DEFAULT_DURATION = 4000
const ACTION_DURATION = 10000

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

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastEntry
  onDismiss: (id: number) => void
}) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (toast.duration > 0) {
      timerRef.current = setTimeout(() => onDismiss(toast.id), toast.duration)
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [toast.id, toast.duration, onDismiss])

  const handleAction = () => {
    toast.action?.onClick()
    onDismiss(toast.id)
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 80, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
      className={cn(
        'pointer-events-auto w-80 bg-surface border border-border rounded-lg shadow-xl',
        'border-l-[3px]',
        BORDER_COLORS[toast.type],
      )}
      role={toast.type === 'error' ? 'alert' : 'status'}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        {ICONS[toast.type]}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-heading">{toast.title}</div>
          {toast.description && (
            <div className="text-[11px] text-muted mt-0.5">{toast.description}</div>
          )}
          {toast.action && (
            <button
              type="button"
              onClick={handleAction}
              className="mt-2 text-[11px] font-medium text-accent hover:text-accent/80 bg-transparent border-none cursor-pointer p-0"
            >
              {toast.action.label}
            </button>
          )}
        </div>
        <button
          type="button"
          aria-label="Dismiss notification"
          onClick={() => onDismiss(toast.id)}
          className="p-0.5 text-muted hover:text-heading bg-transparent border-none cursor-pointer shrink-0"
        >
          <X size={12} />
        </button>
      </div>
    </motion.div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([])

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(
    (type: ToastType, title: string, description?: string, options?: ToastOptions): number => {
      const id = ++toastId
      const duration = options?.duration ?? (options?.action ? ACTION_DURATION : DEFAULT_DURATION)
      setToasts((prev) => [
        ...prev,
        { id, type, title, description, action: options?.action, duration },
      ])
      return id
    },
    [],
  )

  const ctx: ToastContextType = {
    toast: addToast,
    success: (title, desc, opts) => addToast('success', title, desc, opts),
    error: (title, desc, opts) => addToast('error', title, desc, opts),
    warning: (title, desc, opts) => addToast('warning', title, desc, opts),
    info: (title, desc, opts) => addToast('info', title, desc, opts),
    dismiss: remove,
  }

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => (
            <ToastItem key={t.id} toast={t} onDismiss={remove} />
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
