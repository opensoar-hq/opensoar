import { cn } from '@/lib/utils'

interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  className?: string
}

export function Select({ value, onChange, options, className }: SelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'px-2.5 py-1.5 text-xs rounded-md border border-border bg-surface text-text',
        'cursor-pointer focus:outline-none focus:border-accent',
        className,
      )}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}
