import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Tab {
  value: string
  label: string
  icon?: ReactNode
}

interface TabsProps {
  value: string
  onChange: (value: string) => void
  tabs: Tab[]
  className?: string
}

export function Tabs({ value, onChange, tabs, className }: TabsProps) {
  return (
    <div className={cn('flex gap-0.5 border-b border-border', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={cn(
            'flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors',
            'bg-transparent border-x-0 border-t-0 cursor-pointer',
            value === tab.value
              ? 'text-heading border-accent'
              : 'text-muted border-transparent hover:text-heading hover:border-border',
          )}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  )
}
