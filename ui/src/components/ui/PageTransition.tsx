import { motion, type Variants } from 'framer-motion'
import type { ReactNode } from 'react'

const ease = [0.25, 0.1, 0.25, 1] as [number, number, number, number]

const pageVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease },
  },
  exit: {
    opacity: 0,
    y: -4,
    transition: { duration: 0.15, ease },
  },
}

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {children}
    </motion.div>
  )
}

// For staggering child elements (cards, rows, etc.)
const staggerParentVariants: Variants = {
  initial: {},
  animate: {
    transition: { staggerChildren: 0.05 },
  },
}

const staggerChildVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease },
  },
}

export function StaggerParent({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      variants={staggerParentVariants}
      initial="initial"
      animate="animate"
      className={className}
    >
      {children}
    </motion.div>
  )
}

export function StaggerChild({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={staggerChildVariants} className={className}>
      {children}
    </motion.div>
  )
}
