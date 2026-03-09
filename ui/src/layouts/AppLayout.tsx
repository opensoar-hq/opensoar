import { useState } from 'react'
import { Outlet } from 'react-router'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Shield, Play, BookOpen, Settings,
  LogOut, User, ShieldCheck,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import {
  Sidebar,
  SidebarBody,
  SidebarLink,
  SidebarLabel,
  useSidebar,
} from '@/components/ui/Sidebar'

const navItems = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} />, end: true },
  { to: '/alerts', label: 'Alerts', icon: <Shield size={18} /> },
  { to: '/runs', label: 'Runs', icon: <Play size={18} /> },
  { to: '/playbooks', label: 'Playbooks', icon: <BookOpen size={18} /> },
]

function SidebarContent() {
  const { analyst, logout } = useAuth()
  const { open, animate } = useSidebar()

  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-2 py-1 mb-2">
        <div className="w-5 h-5 rounded-md bg-accent flex items-center justify-center flex-shrink-0">
          <ShieldCheck size={12} className="text-bg" />
        </div>
        <motion.span
          animate={{
            display: animate ? (open ? 'inline-block' : 'none') : 'inline-block',
            opacity: animate ? (open ? 1 : 0) : 1,
          }}
          transition={{ duration: 0.15 }}
          className="font-semibold text-[15px] text-heading tracking-tight whitespace-pre select-none"
        >
          OpenSOAR
        </motion.span>
      </div>

      {/* Nav */}
      <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden mt-2">
        <SidebarLabel>Navigation</SidebarLabel>
        <div className="flex flex-col gap-0.5">
          {navItems.map((item) => (
            <SidebarLink
              key={item.to}
              to={item.to}
              icon={item.icon}
              label={item.label}
              end={item.end}
            />
          ))}
        </div>
      </div>

      {/* Bottom section — settings + user */}
      <div className="border-t border-border pt-3 mt-3 flex flex-col gap-0.5">
        {analyst?.role === 'admin' && (
          <SidebarLink
            to="/settings"
            icon={<Settings size={18} />}
            label="Settings"
          />
        )}
        <div className="flex items-center gap-2.5 px-2 py-1.5 mt-1">
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-accent/15 text-accent flex-shrink-0">
            <User size={12} />
          </span>
          <motion.div
            animate={{
              display: animate ? (open ? 'block' : 'none') : 'block',
              opacity: animate ? (open ? 1 : 0) : 1,
            }}
            transition={{ duration: 0.15 }}
            className="min-w-0 whitespace-pre"
          >
            <div className="text-xs font-medium text-heading truncate">
              {analyst?.display_name}
            </div>
            <div className="text-[10px] text-muted flex items-center gap-1">
              @{analyst?.username}
              {analyst?.role === 'admin' && (
                <span className="text-[9px] text-accent bg-accent/10 px-1 py-px rounded font-medium">
                  admin
                </span>
              )}
            </div>
          </motion.div>
        </div>
        <SidebarLink
          icon={<LogOut size={16} />}
          label="Sign out"
          onClick={logout}
          className="text-muted hover:text-danger"
        />
      </div>
    </>
  )
}

export function AppLayout() {
  const [open, setOpen] = useState(false)

  return (
    <div className={cn('flex flex-col md:flex-row h-screen w-full overflow-hidden')}>
      <Sidebar open={open} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-0">
          <SidebarContent />
        </SidebarBody>
      </Sidebar>
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-[1400px] w-full mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
