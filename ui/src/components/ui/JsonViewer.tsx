import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

function JsonNode({ name, value, depth = 0 }: { name?: string; value: unknown; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2)

  if (value === null) {
    return (
      <div className="flex" style={{ paddingLeft: depth * 16 }}>
        {name && <span className="text-muted mr-1">{name}:</span>}
        <span className="text-muted italic">null</span>
      </div>
    )
  }

  if (typeof value === 'boolean') {
    return (
      <div className="flex" style={{ paddingLeft: depth * 16 }}>
        {name && <span className="text-muted mr-1">{name}:</span>}
        <span className="text-warning">{String(value)}</span>
      </div>
    )
  }

  if (typeof value === 'number') {
    return (
      <div className="flex" style={{ paddingLeft: depth * 16 }}>
        {name && <span className="text-muted mr-1">{name}:</span>}
        <span className="text-accent">{value}</span>
      </div>
    )
  }

  if (typeof value === 'string') {
    return (
      <div className="flex" style={{ paddingLeft: depth * 16 }}>
        {name && <span className="text-muted mr-1">{name}:</span>}
        <span className="text-success">"{value}"</span>
      </div>
    )
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <div className="flex" style={{ paddingLeft: depth * 16 }}>
          {name && <span className="text-muted mr-1">{name}:</span>}
          <span className="text-muted">[]</span>
        </div>
      )
    }
    return (
      <div style={{ paddingLeft: depth * 16 }}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-0.5 text-muted hover:text-heading bg-transparent border-none cursor-pointer p-0 font-mono text-xs"
        >
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {name && <span className="mr-1">{name}:</span>}
          <span>[{value.length}]</span>
        </button>
        {expanded && value.map((item, i) => (
          <JsonNode key={i} name={String(i)} value={item} depth={depth + 1} />
        ))}
      </div>
    )
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) {
      return (
        <div className="flex" style={{ paddingLeft: depth * 16 }}>
          {name && <span className="text-muted mr-1">{name}:</span>}
          <span className="text-muted">{'{}'}</span>
        </div>
      )
    }
    return (
      <div style={{ paddingLeft: depth * 16 }}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-0.5 text-muted hover:text-heading bg-transparent border-none cursor-pointer p-0 font-mono text-xs"
        >
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {name && <span className="mr-1">{name}:</span>}
          <span>{`{${entries.length}}`}</span>
        </button>
        {expanded && entries.map(([k, v]) => (
          <JsonNode key={k} name={k} value={v} depth={depth + 1} />
        ))}
      </div>
    )
  }

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      {name && <span className="text-muted mr-1">{name}:</span>}
      <span>{String(value)}</span>
    </div>
  )
}

export function JsonViewer({ data, className }: { data: unknown; className?: string }) {
  return (
    <div className={cn('font-mono text-xs leading-5 p-3 rounded-md bg-bg overflow-auto', className)}>
      <JsonNode value={data} />
    </div>
  )
}
