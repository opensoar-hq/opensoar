/* eslint-disable react-refresh/only-export-components */
import React, { useState, createContext, useContext } from 'react'
import { NavLink } from 'react-router'
import { AnimatePresence, motion } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SidebarContextProps {
  open: boolean
  setOpen: React.Dispatch<React.SetStateAction<boolean>>
  animate: boolean
}

const SidebarContext = createContext<SidebarContextProps | undefined>(undefined)

export const useSidebar = () => {
  const context = useContext(SidebarContext)
  if (!context) throw new Error('useSidebar must be used within a SidebarProvider')
  return context
}

export const SidebarProvider = ({
  children,
  open: openProp,
  setOpen: setOpenProp,
  animate = true,
}: {
  children: React.ReactNode
  open?: boolean
  setOpen?: React.Dispatch<React.SetStateAction<boolean>>
  animate?: boolean
}) => {
  const [openState, setOpenState] = useState(false)
  const open = openProp !== undefined ? openProp : openState
  const setOpen = setOpenProp !== undefined ? setOpenProp : setOpenState

  return (
    <SidebarContext.Provider value={{ open, setOpen, animate }}>
      {children}
    </SidebarContext.Provider>
  )
}

export const Sidebar = ({
  children,
  open,
  setOpen,
  animate,
}: {
  children: React.ReactNode
  open?: boolean
  setOpen?: React.Dispatch<React.SetStateAction<boolean>>
  animate?: boolean
}) => {
  return (
    <SidebarProvider open={open} setOpen={setOpen} animate={animate}>
      {children}
    </SidebarProvider>
  )
}

export const SidebarBody = (props: React.ComponentProps<typeof motion.div>) => {
  return (
    <>
      <DesktopSidebar {...props} />
      <MobileSidebar {...(props as React.ComponentProps<'div'>)} />
    </>
  )
}

export const DesktopSidebar = ({
  className,
  children,
  ...props
}: React.ComponentProps<typeof motion.div>) => {
  const { open, setOpen, animate } = useSidebar()
  return (
    <motion.div
      className={cn(
        'h-full px-3 py-4 hidden md:flex md:flex-col bg-surface border-r border-border flex-shrink-0',
        className,
      )}
      animate={{
        width: animate ? (open ? '240px' : '60px') : '240px',
      }}
      transition={{
        duration: 0.25,
        ease: [0.25, 0.1, 0.25, 1],
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export const MobileSidebar = ({
  className,
  children,
  ...props
}: React.ComponentProps<'div'>) => {
  const { open, setOpen } = useSidebar()
  return (
    <>
      <div
        className="h-12 px-4 py-3 flex md:hidden items-center justify-between bg-surface border-b border-border w-full"
        {...props}
      >
        <div className="flex justify-end z-20 w-full">
          <Menu
            className="text-heading cursor-pointer"
            size={20}
            onClick={() => setOpen(!open)}
          />
        </div>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ x: '-100%', opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: '-100%', opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
              className={cn(
                'fixed h-full w-full inset-0 bg-surface p-8 z-[100] flex flex-col justify-between',
                className,
              )}
            >
              <div
                className="absolute right-6 top-4 z-50 text-heading cursor-pointer"
                onClick={() => setOpen(!open)}
              >
                <X size={20} />
              </div>
              {children}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  )
}

export const SidebarLink = ({
  to,
  icon,
  label,
  end,
  onClick,
  className,
}: {
  to?: string
  icon: React.ReactNode
  label: string
  end?: boolean
  onClick?: () => void
  className?: string
}) => {
  const { open, animate } = useSidebar()

  // If it's a button (like logout), render as button
  if (!to) {
    return (
      <button
        onClick={onClick}
        className={cn(
          'flex items-center gap-3 py-2 px-2 rounded-md w-full',
          'text-text hover:text-heading hover:bg-surface-hover',
          'bg-transparent border-none cursor-pointer transition-colors duration-150',
          className,
        )}
      >
        <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
          {icon}
        </span>
        <motion.span
          animate={{
            display: animate ? (open ? 'inline-block' : 'none') : 'inline-block',
            opacity: animate ? (open ? 1 : 0) : 1,
          }}
          transition={{ duration: 0.15 }}
          className="text-sm whitespace-pre"
        >
          {label}
        </motion.span>
      </button>
    )
  }

  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => cn(
        'flex items-center gap-3 py-2 px-2 rounded-md no-underline',
        'transition-colors duration-150',
        isActive
          ? 'text-heading bg-accent/10 font-medium'
          : 'text-text hover:text-heading hover:bg-surface-hover',
        className,
      )}
    >
      {({ isActive }) => (
        <>
          <span className={cn(
            'flex-shrink-0 w-5 h-5 flex items-center justify-center',
            isActive && 'text-accent',
          )}>
            {icon}
          </span>
          <motion.span
            animate={{
              display: animate ? (open ? 'inline-block' : 'none') : 'inline-block',
              opacity: animate ? (open ? 1 : 0) : 1,
            }}
            transition={{ duration: 0.15 }}
            className="text-sm whitespace-pre"
          >
            {label}
          </motion.span>
          {isActive && (
            <motion.div
              layoutId="sidebar-active"
              className="absolute left-0 w-[3px] h-5 rounded-r-full bg-accent"
              transition={{ type: 'spring', stiffness: 350, damping: 30 }}
            />
          )}
        </>
      )}
    </NavLink>
  )
}

export const SidebarLabel = ({ children }: { children: React.ReactNode }) => {
  const { open, animate } = useSidebar()
  return (
    <motion.div
      animate={{
        height: animate ? (open ? 'auto' : 0) : 'auto',
        opacity: animate ? (open ? 1 : 0) : 1,
        marginTop: animate ? (open ? 16 : 8) : 16,
        marginBottom: animate ? (open ? 6 : 0) : 6,
      }}
      transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
      className="overflow-hidden text-[10px] uppercase tracking-wider text-muted font-medium px-2 whitespace-pre"
    >
      {children}
    </motion.div>
  )
}
