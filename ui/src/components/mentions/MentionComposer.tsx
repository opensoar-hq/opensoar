import { useEffect, useRef, useState } from 'react'
import { api, type MentionableAnalyst } from '@/api'
import { Input } from '@/components/ui/Input'
import { cn } from '@/lib/utils'

interface MentionComposerProps {
  value: string
  onChange: (next: string) => void
  onSubmit?: () => void
  placeholder?: string
  className?: string
  autoFocus?: boolean
}

/**
 * Comment composer with inline `@username` autocomplete.
 *
 * The dropdown appears whenever the caret sits inside an `@token` at the end
 * of a word.  Arrow keys move through suggestions, Enter/Tab accepts, Escape
 * dismisses.  Outside a mention, Enter calls `onSubmit` so parent pages keep
 * their current "enter to post" behavior.
 */
export function MentionComposer({
  value,
  onChange,
  onSubmit,
  placeholder,
  className,
  autoFocus,
}: MentionComposerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<MentionableAnalyst[]>([])
  const [activeIndex, setActiveIndex] = useState(0)

  // Detect an active `@token` at the caret so we know whether to open the menu.
  function detectQuery(next: string, caret: number): string | null {
    const before = next.slice(0, caret)
    const at = before.lastIndexOf('@')
    if (at < 0) return null
    // `@` must be at the start or follow whitespace so email addresses stay quiet.
    const prev = at === 0 ? ' ' : before[at - 1]
    if (!/\s/.test(prev)) return null
    const token = before.slice(at + 1)
    if (/\s/.test(token)) return null
    return token
  }

  useEffect(() => {
    if (query === null) return
    let cancelled = false
    api.auth
      .mentionable(query || undefined)
      .then((rows) => {
        if (!cancelled) {
          setSuggestions(rows)
          setActiveIndex(0)
        }
      })
      .catch(() => {
        if (!cancelled) setSuggestions([])
      })
    return () => {
      cancelled = true
    }
  }, [query])

  const showMenu = query !== null && suggestions.length > 0

  function applyMention(username: string) {
    const input = inputRef.current
    if (!input) return
    const caret = input.selectionStart ?? value.length
    const before = value.slice(0, caret)
    const at = before.lastIndexOf('@')
    if (at < 0) return
    const next = `${value.slice(0, at)}@${username} ${value.slice(caret)}`
    onChange(next)
    setQuery(null)
    setSuggestions([])
    // Restore caret just after the inserted mention + trailing space.
    const newCaret = at + username.length + 2
    requestAnimationFrame(() => {
      input.focus()
      input.setSelectionRange(newCaret, newCaret)
    })
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (showMenu) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((i) => (i + 1) % suggestions.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((i) => (i - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        applyMention(suggestions[activeIndex].username)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setQuery(null)
        return
      }
    }
    if (e.key === 'Enter' && !showMenu && value.trim() && onSubmit) {
      e.preventDefault()
      onSubmit()
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.value
    onChange(next)
    setQuery(detectQuery(next, e.target.selectionStart ?? next.length))
  }

  return (
    <div className={cn('relative', className)}>
      <Input
        ref={inputRef}
        type="text"
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onBlur={() => setTimeout(() => setQuery(null), 120)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className="text-sm"
      />
      {showMenu && (
        <div
          role="listbox"
          data-testid="mention-suggestions"
          className="absolute left-0 right-0 bottom-full mb-1 max-h-48 overflow-y-auto rounded-md border border-border bg-surface shadow-lg z-20"
        >
          {suggestions.map((person, index) => (
            <button
              key={person.id}
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(e) => {
                e.preventDefault()
                applyMention(person.username)
              }}
              onMouseEnter={() => setActiveIndex(index)}
              className={cn(
                'w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 border-none bg-transparent cursor-pointer',
                index === activeIndex ? 'bg-surface-hover text-heading' : 'text-text',
              )}
            >
              <span className="font-medium">@{person.username}</span>
              <span className="text-muted">{person.display_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

