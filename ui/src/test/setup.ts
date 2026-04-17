import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import React from 'react'

// Node 25+ ships a stub `localStorage` on globalThis that lacks the DOM
// `Storage` interface (no getItem/setItem/clear). jsdom inherits that broken
// object, so we install a simple in-memory replacement for tests.
class MemoryStorage implements Storage {
  private store = new Map<string, string>()
  get length() {
    return this.store.size
  }
  clear(): void {
    this.store.clear()
  }
  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null
  }
  removeItem(key: string): void {
    this.store.delete(key)
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }
}

const storage = new MemoryStorage()
Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: storage,
})
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: storage,
  })
}

afterEach(() => {
  cleanup()
  storage.clear()
  vi.restoreAllMocks()
})

// JSDOM lacks matchMedia which some Tailwind / framer-motion helpers call.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

// Avoid framer-motion LayoutGroup / animation complaints in jsdom.
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}

// jsdom does not implement scrollTo — stub it to silence warnings from
// components that scroll on interaction.
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
Element.prototype.scrollTo = vi.fn() as unknown as Element['scrollTo']
Element.prototype.scrollIntoView = vi.fn() as unknown as Element['scrollIntoView']

// Strip the framer-motion animation props that would otherwise be warned about
// when forwarded to a plain DOM element.
const MOTION_PROPS = new Set([
  'initial',
  'animate',
  'exit',
  'transition',
  'layout',
  'layoutId',
  'variants',
  'whileHover',
  'whileTap',
  'whileFocus',
  'whileInView',
  'drag',
  'dragConstraints',
])

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function stripMotionProps(props: Record<string, any>): Record<string, any> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const clean: Record<string, any> = {}
  for (const key of Object.keys(props)) {
    if (!MOTION_PROPS.has(key)) clean[key] = props[key]
  }
  return clean
}

// Stub framer-motion so tests don't wait on layout/exit animations.
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('framer-motion')
  const componentCache = new Map<string, React.ComponentType<unknown>>()
  const makeComponent = (tag: string) => {
    const cached = componentCache.get(tag)
    if (cached) return cached
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Component = React.forwardRef<unknown, any>((props, ref) =>
      React.createElement(tag, { ...stripMotionProps(props), ref }),
    )
    Component.displayName = `motion.${tag}`
    componentCache.set(tag, Component as unknown as React.ComponentType<unknown>)
    return Component
  }

  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    motion: new Proxy(
      {},
      {
        get: (_target, tag: string) => makeComponent(tag),
      },
    ),
  }
})
