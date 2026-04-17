import { Fragment } from 'react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'

interface MentionTextProps {
  text: string
  /** Usernames validated server-side. Only these render as linked pills. */
  mentions?: string[]
  className?: string
}

const MENTION_PATTERN = /(?<![\w@.])@([A-Za-z0-9_][A-Za-z0-9_.-]{0,63})/g

/**
 * Render comment text with validated `@username` tokens promoted to pills
 * linking to the analyst profile.  Tokens that weren't resolved server-side
 * render as plain text so unknown mentions don't mislead operators.
 */
export function MentionText({ text, mentions = [], className }: MentionTextProps) {
  const resolved = new Set(mentions.map((m) => m.toLowerCase()))
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let key = 0

  for (const match of text.matchAll(MENTION_PATTERN)) {
    const index = match.index ?? 0
    const username = match[1].replace(/[._-]+$/, '')
    if (!username) continue
    if (index > lastIndex) {
      parts.push(<Fragment key={key++}>{text.slice(lastIndex, index)}</Fragment>)
    }
    const lower = username.toLowerCase()
    if (resolved.has(lower)) {
      parts.push(
        <Link
          key={key++}
          to={`/settings/analysts/${lower}`}
          data-testid="mention-pill"
          className="inline-flex items-center px-1.5 py-0.5 rounded bg-accent/15 text-accent hover:bg-accent/25 hover:no-underline transition-colors font-medium"
        >
          @{username}
        </Link>,
      )
    } else {
      parts.push(
        <Fragment key={key++}>{`@${username}`}</Fragment>,
      )
    }
    lastIndex = index + match[0].length
    // Trailing punctuation we stripped for username — push it back as text.
    const trailing = match[0].slice(1 + username.length)
    if (trailing) {
      parts.push(<Fragment key={key++}>{trailing}</Fragment>)
    }
  }
  if (lastIndex < text.length) {
    parts.push(<Fragment key={key++}>{text.slice(lastIndex)}</Fragment>)
  }

  return <span className={cn(className)}>{parts}</span>
}
