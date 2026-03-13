"use client"

import { useState } from 'react'
import {
  CheckCircle2,
  Circle,
  CircleAlert,
  CircleDotDashed,
  CircleX,
  Clock,
  Timer,
  ChevronDown,
  ChevronRight,
  Terminal,
  Repeat,
} from 'lucide-react'
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion'
import { cn } from '@/lib/utils'
import { JsonViewer } from '@/components/ui/JsonViewer'
import { formatDate } from '@/lib/utils'

// Types matching our PlaybookRun / ActionResult API models
interface ActionStep {
  id: string
  action_name: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  error: string | null
  attempt: number
}

interface RunPlan {
  id: string
  playbook_name: string
  status: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  result: Record<string, unknown> | null
  steps: ActionStep[]
}

// Status icon component with animation
function StatusIcon({ status, size = 'md' }: { status: string; size?: 'sm' | 'md' }) {
  const iconClass = size === 'sm' ? 'h-3.5 w-3.5' : 'h-[18px] w-[18px]'

  const icon = (() => {
    switch (status) {
      case 'completed':
      case 'success':
        return <CheckCircle2 className={cn(iconClass, 'text-success')} />
      case 'running':
      case 'in-progress':
        return <CircleDotDashed className={cn(iconClass, 'text-info')} />
      case 'failed':
        return <CircleX className={cn(iconClass, 'text-danger')} />
      case 'warning':
      case 'need-help':
        return <CircleAlert className={cn(iconClass, 'text-warning')} />
      default:
        return <Circle className={cn(iconClass, 'text-muted')} />
    }
  })()

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={status}
        initial={{ opacity: 0, scale: 0.8, rotate: -10 }}
        animate={{ opacity: 1, scale: 1, rotate: 0 }}
        exit={{ opacity: 0, scale: 0.8, rotate: 10 }}
        transition={{ duration: 0.2, ease: [0.2, 0.65, 0.3, 0.9] }}
      >
        {icon}
      </motion.div>
    </AnimatePresence>
  )
}

// Status badge with animation
function StatusPill({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    completed: 'bg-success/15 text-success',
    success: 'bg-success/15 text-success',
    running: 'bg-info/15 text-info',
    'in-progress': 'bg-info/15 text-info',
    failed: 'bg-danger/15 text-danger',
    pending: 'bg-border/40 text-muted',
  }

  return (
    <motion.span
      className={cn(
        'rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
        colorMap[status] || 'bg-border/40 text-muted',
      )}
      key={status}
      initial={{ scale: 1 }}
      animate={{ scale: [1, 1.06, 1] }}
      transition={{ duration: 0.3, ease: [0.34, 1.56, 0.64, 1] }}
    >
      {status.replace('_', ' ')}
    </motion.span>
  )
}

function formatMs(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

// Step detail section (expandable)
function StepDetails({ step }: { step: ActionStep }) {
  return (
    <motion.div
      className="ml-6 mt-1 border-l-2 border-dashed border-border/50 pl-4 pb-1 overflow-hidden"
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: [0.2, 0.65, 0.3, 0.9] }}
    >
      {/* Timing */}
      <div className="flex gap-4 text-[11px] text-muted py-1.5">
        {step.started_at && (
          <span className="flex items-center gap-1">
            <Clock size={10} /> {formatDate(step.started_at)}
          </span>
        )}
        {step.duration_ms != null && (
          <span className="flex items-center gap-1">
            <Timer size={10} /> {formatMs(step.duration_ms)}
          </span>
        )}
        {step.attempt > 1 && (
          <span className="flex items-center gap-1 text-warning">
            <Repeat size={10} /> attempt {step.attempt}
          </span>
        )}
      </div>

      {/* Input */}
      {step.input_data && Object.keys(step.input_data).length > 0 && (
        <div className="mt-1.5">
          <div className="text-[10px] text-muted uppercase tracking-wide mb-1 flex items-center gap-1">
            <Terminal size={9} /> Input
          </div>
          <JsonViewer data={step.input_data} className="text-[11px]" />
        </div>
      )}

      {/* Output */}
      {step.output_data && Object.keys(step.output_data).length > 0 && (
        <div className="mt-2">
          <div className="text-[10px] text-muted uppercase tracking-wide mb-1 flex items-center gap-1">
            <Terminal size={9} /> Output
          </div>
          <JsonViewer data={step.output_data} className="text-[11px]" />
        </div>
      )}

      {/* Error */}
      {step.error && (
        <div className="mt-2">
          <div className="text-[10px] text-danger uppercase tracking-wide mb-1">Error</div>
          <pre className="text-[11px] font-mono bg-danger/10 text-danger p-2.5 rounded-md overflow-auto whitespace-pre-wrap m-0">
            {step.error}
          </pre>
        </div>
      )}
    </motion.div>
  )
}

// Easing curve
const ease = [0.2, 0.65, 0.3, 0.9] as [number, number, number, number]

// Animation variants
const stepListVariants = {
  hidden: { opacity: 0, height: 0, overflow: 'hidden' as const },
  visible: {
    height: 'auto',
    opacity: 1,
    overflow: 'visible' as const,
    transition: {
      duration: 0.25,
      staggerChildren: 0.04,
      when: 'beforeChildren' as const,
      ease,
    },
  },
  exit: {
    height: 0,
    opacity: 0,
    overflow: 'hidden' as const,
    transition: { duration: 0.2, ease },
  },
}

const stepVariants = {
  hidden: { opacity: 0, x: -8 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { type: 'spring' as const, stiffness: 500, damping: 25 },
  },
  exit: { opacity: 0, x: -8, transition: { duration: 0.15 } },
}

export function ExecutionPlan({ run }: { run: RunPlan }) {
  const [expanded, setExpanded] = useState(true)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>(() => {
    // Auto-expand failed steps
    const initial: Record<string, boolean> = {}
    run.steps.forEach((s) => {
      if (s.status === 'failed') initial[s.id] = true
    })
    return initial
  })

  const toggleStep = (id: string) => {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const completedCount = run.steps.filter(
    (s) => s.status === 'completed' || s.status === 'success',
  ).length
  const failedCount = run.steps.filter((s) => s.status === 'failed').length

  return (
    <motion.div
      className="bg-surface border border-border rounded-lg shadow overflow-hidden"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.2, 0.65, 0.3, 0.9] }}
    >
      <LayoutGroup>
        <div className="overflow-hidden">
          {/* Run header row */}
          <motion.div
            className="group flex items-center px-4 py-3 cursor-pointer"
            onClick={() => setExpanded(!expanded)}
            whileHover={{
              backgroundColor: 'rgba(255,255,255,0.02)',
              transition: { duration: 0.15 },
            }}
          >
            <div className="mr-3 flex-shrink-0">
              <StatusIcon status={run.status} size="md" />
            </div>
            <div className="flex-1 min-w-0 flex items-center gap-3">
              <span className="text-sm font-medium text-heading truncate">
                {run.playbook_name}
              </span>
              {run.steps.length > 0 && (
                <span className="text-[11px] text-muted">
                  {completedCount}/{run.steps.length} steps
                  {failedCount > 0 && (
                    <span className="text-danger ml-1">({failedCount} failed)</span>
                  )}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 ml-2">
              <StatusPill status={run.status} />
              <motion.div
                animate={{ rotate: expanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
                className="text-muted"
              >
                <ChevronDown size={14} />
              </motion.div>
            </div>
          </motion.div>

          {/* Steps list */}
          <AnimatePresence mode="wait">
            {expanded && run.steps.length > 0 && (
              <motion.div
                className="relative"
                variants={stepListVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                layout
              >
                {/* Vertical connecting line */}
                <div className="absolute top-0 bottom-3 left-[26px] border-l-2 border-dashed border-border/40" />

                <ul className="border-t border-border mx-2 mb-2 space-y-0">
                  {run.steps.map((step, i) => {
                    const isStepExpanded = expandedSteps[step.id]

                    return (
                      <motion.li
                        key={step.id}
                        className="flex flex-col py-0.5 pl-5"
                        variants={stepVariants}
                        layout
                      >
                        <motion.div
                          className="flex items-center rounded-md px-2 py-1.5 cursor-pointer"
                          onClick={() => toggleStep(step.id)}
                          whileHover={{
                            backgroundColor: 'rgba(255,255,255,0.02)',
                            transition: { duration: 0.15 },
                          }}
                          layout
                        >
                          {/* Step status icon */}
                          <motion.div
                            className="mr-2 flex-shrink-0"
                            whileTap={{ scale: 0.9 }}
                            layout
                          >
                            <StatusIcon status={step.status} size="sm" />
                          </motion.div>

                          {/* Step number */}
                          <span className="text-[10px] text-muted font-mono mr-2 w-4 text-right shrink-0">
                            {i + 1}
                          </span>

                          {/* Action name */}
                          <span
                            className={cn(
                              'text-xs font-mono flex-1 truncate',
                              step.status === 'completed' || step.status === 'success'
                                ? 'text-muted line-through'
                                : step.status === 'failed'
                                  ? 'text-danger'
                                  : 'text-heading',
                            )}
                          >
                            {step.action_name}
                          </span>

                          {/* Duration pill */}
                          {step.duration_ms != null && (
                            <span className="text-[10px] font-mono text-muted bg-bg px-1.5 py-0.5 rounded ml-2">
                              {formatMs(step.duration_ms)}
                            </span>
                          )}

                          {/* Retry badge */}
                          {step.attempt > 1 && (
                            <motion.span
                              className="text-[9px] text-warning bg-warning/15 px-1 py-0.5 rounded ml-1.5 font-medium"
                              initial={{ opacity: 0, scale: 0.9 }}
                              animate={{ opacity: 1, scale: 1 }}
                              whileHover={{ y: -1, transition: { duration: 0.15 } }}
                            >
                              ×{step.attempt}
                            </motion.span>
                          )}

                          {/* Expand indicator */}
                          <motion.div
                            className="ml-2 text-muted"
                            animate={{ rotate: isStepExpanded ? 90 : 0 }}
                            transition={{ duration: 0.15 }}
                          >
                            <ChevronRight size={12} />
                          </motion.div>
                        </motion.div>

                        {/* Expandable step details */}
                        <AnimatePresence>
                          {isStepExpanded && <StepDetails step={step} />}
                        </AnimatePresence>
                      </motion.li>
                    )
                  })}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Run-level error */}
          {run.error && (
            <motion.div
              className="mx-4 mb-3 p-3 bg-danger/5 border border-danger/20 rounded-md"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              <div className="text-[10px] text-danger uppercase tracking-wide mb-1 font-medium">
                Run Error
              </div>
              <pre className="text-[11px] font-mono text-danger whitespace-pre-wrap m-0">
                {run.error}
              </pre>
            </motion.div>
          )}

          {/* Run result */}
          {run.result && Object.keys(run.result).length > 0 && (
            <motion.div
              className="mx-4 mb-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
            >
              <div className="text-[10px] text-muted uppercase tracking-wide mb-1 font-medium">
                Result
              </div>
              <JsonViewer data={run.result} className="text-[11px]" />
            </motion.div>
          )}
        </div>
      </LayoutGroup>
    </motion.div>
  )
}

// Compact version for showing runs inside AlertDetailPage
export function ExecutionPlanCompact({ run, playbookName }: { run: RunPlan; playbookName: string }) {
  const [expanded, setExpanded] = useState(false)
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({})

  const toggleStep = (id: string) => {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const completedCount = run.steps.filter(
    (s) => s.status === 'completed' || s.status === 'success',
  ).length

  return (
    <motion.div
      className="overflow-hidden"
      layout
    >
      {/* Row */}
      <motion.div
        className="flex items-center px-4 py-2.5 cursor-pointer hover:bg-surface-hover transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="mr-2">
          <StatusIcon status={run.status} size="sm" />
        </div>
        <span className="text-xs text-heading flex-1 truncate">{playbookName}</span>
        <span className="text-[10px] text-muted mr-2">
          {completedCount}/{run.steps.length}
        </span>
        <StatusPill status={run.status} />
        <motion.div
          className="ml-2 text-muted"
          animate={{ rotate: expanded ? 90 : 0 }}
          transition={{ duration: 0.15 }}
        >
          <ChevronRight size={12} />
        </motion.div>
      </motion.div>

      {/* Inline steps */}
      <AnimatePresence>
        {expanded && run.steps.length > 0 && (
          <motion.div
            className="relative border-t border-border"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: [0.2, 0.65, 0.3, 0.9] }}
          >
            <div className="absolute top-2 bottom-2 left-[30px] border-l border-dashed border-border/40" />
            <ul className="py-1 pl-4 pr-3 space-y-0">
              {run.steps.map((step, i) => (
                <motion.li
                  key={step.id}
                  className="flex flex-col"
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <div
                    className="flex items-center py-1 px-2 rounded cursor-pointer hover:bg-surface-hover/50 transition-colors"
                    onClick={(e) => { e.stopPropagation(); toggleStep(step.id) }}
                  >
                    <div className="mr-1.5">
                      <StatusIcon status={step.status} size="sm" />
                    </div>
                    <span className={cn(
                      'text-[11px] font-mono flex-1 truncate',
                      (step.status === 'completed' || step.status === 'success') && 'text-muted line-through',
                    )}>
                      {step.action_name}
                    </span>
                    {step.duration_ms != null && (
                      <span className="text-[9px] font-mono text-muted ml-1">
                        {formatMs(step.duration_ms)}
                      </span>
                    )}
                  </div>
                  <AnimatePresence>
                    {expandedSteps[step.id] && <StepDetails step={step} />}
                  </AnimatePresence>
                </motion.li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
