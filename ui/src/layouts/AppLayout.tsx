import { useState } from 'react'
import { Outlet } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Shield, Play, BookOpen, Briefcase, Settings,
  LogOut, User, ShieldCheck, KeyRound,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { api } from '@/api'
import {
  Sidebar,
  SidebarBody,
  SidebarLink,
  SidebarLabel,
  useSidebar,
} from '@/components/ui/Sidebar'
import { Button } from '@/components/ui/Button'
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog'
import { Input, Label } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { useToast } from '@/components/ui/Toast'

const navItems = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} />, end: true },
  { to: '/alerts', label: 'Alerts', icon: <Shield size={18} /> },
  { to: '/runs', label: 'Runs', icon: <Play size={18} /> },
  { to: '/playbooks', label: 'Playbooks', icon: <BookOpen size={18} /> },
  { to: '/incidents', label: 'Incidents', icon: <Briefcase size={18} /> },
]

function SidebarContent() {
  const { analyst, authCapabilities, logout } = useAuth()
  const { tenants, selectedTenantId, setSelectedTenantId } = useWorkspace()
  const { open, animate } = useSidebar()
  const toast = useToast()
  const [showPasswordDialog, setShowPasswordDialog] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')

  const changePasswordMutation = useMutation({
    mutationFn: () => api.auth.changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    }),
    onSuccess: () => {
      setShowPasswordDialog(false)
      setCurrentPassword('')
      setNewPassword('')
      toast.success('Password updated')
    },
    onError: () => {
      toast.error('Failed to update password')
    },
  })

  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-2 py-1 mb-2">
        <ShieldCheck size={18} className="text-heading flex-shrink-0" />
        <motion.span
          animate={{
            display: animate ? (open ? 'inline-block' : 'none') : 'inline-block',
            opacity: animate ? (open ? 1 : 0) : 1,
          }}
          transition={{ duration: 0.15 }}
          className="text-[15px] text-heading whitespace-pre select-none"
          style={{ fontFamily: "'Inter Tight', sans-serif", letterSpacing: '-0.03em' }}
        >
          <span style={{ fontWeight: 400 }}>Open</span><span style={{ fontWeight: 700 }}>SOAR</span>
        </motion.span>
      </div>

      {/* Nav */}
      <div className="flex flex-col flex-1 overflow-y-auto overflow-x-hidden mt-2">
        {tenants.length > 0 && (
          <div className="px-2 mb-3">
            <motion.div
              animate={{
                display: animate ? (open ? 'block' : 'none') : 'block',
                opacity: animate ? (open ? 1 : 0) : 1,
              }}
              transition={{ duration: 0.15 }}
            >
              <label htmlFor="workspace-switcher" className="block text-[11px] uppercase tracking-wide text-muted mb-1.5">
                Workspace
              </label>
              <Select
                id="workspace-switcher"
                value={selectedTenantId}
                onChange={setSelectedTenantId}
                options={[
                  { value: '', label: analyst?.role === 'admin' ? 'All tenants' : 'All workspaces' },
                  ...tenants.map((tenant) => ({ value: tenant.id, label: tenant.name })),
                ]}
                className="w-full"
              />
            </motion.div>
          </div>
        )}
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
        {(analyst?.role === 'admin' || analyst?.role === 'tenant_admin') && (
          <SidebarLink
            to="/settings"
            icon={<Settings size={18} />}
            label="Settings"
          />
        )}
        <div className="flex items-center gap-2.5 px-2 py-1.5 mt-1">
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-overlay text-heading flex-shrink-0">
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
          icon={<KeyRound size={16} />}
          label="Change password"
          onClick={() => setShowPasswordDialog(true)}
          className="text-muted hover:text-heading"
        />
        <SidebarLink
          icon={<LogOut size={16} />}
          label="Sign out"
          onClick={logout}
          className="text-muted hover:text-danger"
        />
      </div>

      <Dialog open={showPasswordDialog} onClose={() => setShowPasswordDialog(false)}>
        <DialogContent>
          <DialogHeader onClose={() => setShowPasswordDialog(false)}>
            <DialogTitle>Change Password</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="text-xs text-muted">
              {authCapabilities.local_login_enabled
                ? 'Update the local password for this account.'
                : 'Local password login is disabled in this deployment.'}
            </div>
            <div>
              <Label htmlFor="current-password">Current Password</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
          </DialogBody>
          <DialogFooter>
            <Button size="sm" variant="ghost" onClick={() => setShowPasswordDialog(false)}>Cancel</Button>
            <Button
              size="sm"
              variant="primary"
              onClick={() => changePasswordMutation.mutate()}
              disabled={!authCapabilities.local_login_enabled || !currentPassword || !newPassword}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
