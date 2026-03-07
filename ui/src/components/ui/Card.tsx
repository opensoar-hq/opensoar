import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface CardProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className }: CardProps) {
  return (
    <div className={cn('border border-border rounded-lg bg-surface', className)}>
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: CardProps) {
  return (
    <div className={cn('px-5 py-4 border-b border-border', className)}>
      {children}
    </div>
  )
}

export function CardTitle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h3 className={cn('text-sm font-medium text-heading m-0', className)}>
      {children}
    </h3>
  )
}

export function CardContent({ children, className }: CardProps) {
  return (
    <div className={cn('px-5 py-4', className)}>
      {children}
    </div>
  )
}
