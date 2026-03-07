import { Loader } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Spinner({ className, size = 16 }: { className?: string; size?: number }) {
  return <Loader size={size} className={cn('animate-spin text-muted', className)} />
}
