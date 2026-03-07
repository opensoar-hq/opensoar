import { Button } from './Button'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page: number
  total: number
  limit: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, total, limit, onPageChange }: PaginationProps) {
  if (total <= limit) return null

  const totalPages = Math.ceil(total / limit)
  const from = page * limit + 1
  const to = Math.min((page + 1) * limit, total)

  return (
    <div className="flex items-center justify-between mt-4 text-xs text-muted">
      <span>
        Showing <span className="text-heading font-medium">{from}–{to}</span> of <span className="text-heading font-medium">{total}</span>
      </span>
      <div className="flex items-center gap-1">
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
        >
          <ChevronLeft size={14} /> Prev
        </Button>
        <span className="px-2 text-heading font-medium">
          {page + 1} / {totalPages}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onPageChange(page + 1)}
          disabled={(page + 1) * limit >= total}
        >
          Next <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  )
}
