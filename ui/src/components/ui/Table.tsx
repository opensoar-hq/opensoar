import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="border border-border rounded-lg overflow-hidden bg-surface">
      <table className={cn('w-full text-sm', className)} style={{ borderCollapse: 'collapse' }}>
        {children}
      </table>
    </div>
  )
}

export function TableHeader({ children }: { children: ReactNode }) {
  return <thead>{children}</thead>
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>
}

export function TableRow({ children, className, selected, ...props }: {
  children: ReactNode
  className?: string
  selected?: boolean
  onClick?: () => void
}) {
  return (
    <tr
      className={cn(
        'border-b border-border hover:bg-surface-hover transition-colors group',
        selected && 'bg-accent/5',
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  )
}

export function TableHead({ children, className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        'px-3 py-2.5 text-left text-[11px] font-medium uppercase tracking-wide text-muted',
        className,
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export function TableCell({ children, className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn('px-3 py-2.5', className)} {...props}>
      {children}
    </td>
  )
}

export function TableHeaderRow({ children }: { children: ReactNode }) {
  return (
    <tr className="border-b border-border">
      {children}
    </tr>
  )
}
