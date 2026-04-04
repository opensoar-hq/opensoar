import { cn } from '@/lib/utils'

interface SelectProps {
  id?: string
  name?: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  className?: string
}

export function Select({ id, name, value, onChange, options, className }: SelectProps) {
  return (
    <select
      id={id}
      name={name}
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
