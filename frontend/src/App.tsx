import { lazy, Suspense, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { Bell, Boxes, ClipboardList, LayoutDashboard, LogOut, Menu, Network, Plus, Settings2, UserRound, Wrench } from 'lucide-react'
import { Button, EmptyState, ErrorState, Loading } from './components/ui'
import AssetsPage from './features/assets/AssetsPage'
import { RoutingRulesPage, SlaPoliciesPage } from './features/admin/WorkflowConfigPages'
import DashboardPage from './features/issues/DashboardPage'
import { IssueCreatePage, IssueDetailPage, IssueListPage } from './features/issues/IssuePages'
import { WorkOrderDetailPage, WorkOrderListPage } from './features/workorders/WorkOrderPages'
import LoginPage from './features/auth/LoginPage'
import NotificationsPage from './features/notifications/NotificationsPage'
import { NetworkDeviceDetailPage, NetworkDevicesPage, NetworkMeasurementEvaluationPage, NetworkMeasurementsPage, NetworksPage } from './features/network/NetworkPages'
import NetworkQualityPage from './features/network/NetworkQualityPage'
const LandingPage = lazy(() => import('./features/landing/LandingPage'))

function LandingPageRoute() {
  return <Suspense fallback={<main className="full-state"><Loading label="Loading CampusOps" /></main>}><LandingPage /></Suspense>
}
import { ApiError, apiRequest } from './lib/api'
import type { AuthUser, NotificationRecord, Paginated } from './types/api'

type NavigationItem = { label: string; path: string; icon: LucideIcon; end?: boolean }
const adminRoles = new Set<AuthUser['role']>(['ADMIN'])
const assetRoles = new Set<AuthUser['role']>(['ADMIN'])
const workOrderRoles = new Set<AuthUser['role']>(['TECHNICAL_STAFF', 'ADMIN'])
const networkManagementRoles = new Set<AuthUser['role']>(['ADMIN'])
const adminUrl = `${new URL(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api').origin}/admin/`

function navigationFor(user: AuthUser): NavigationItem[] {
  const items: NavigationItem[] = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, end: true },
    { label: user.role === 'STUDENT' || user.role === 'STAFF' ? 'My issues' : 'Issue register', path: '/issues', icon: ClipboardList, end: true },
    { label: 'Report an issue', path: '/issues/new', icon: Plus },
  ]
  if (assetRoles.has(user.role)) items.push({ label: 'Asset register', path: '/assets', icon: Boxes })
  if (workOrderRoles.has(user.role)) items.push({ label: 'Work orders', path: '/work-orders', icon: Wrench, end: true })
  if (canAccessNetwork(user)) {
    items.push({ label: 'Network devices', path: '/network/devices', icon: Network })
    items.push({ label: 'Networks', path: '/network/networks', icon: Network })
    items.push({ label: 'Measurements', path: '/network/measurements', icon: Boxes })
    items.push({ label: 'Network quality', path: '/network-quality', icon: Network })
  }
  if (adminRoles.has(user.role)) {
    items.push({ label: 'Administration', path: '/admin', icon: Settings2 })
    items.push({ label: 'Routing rules', path: '/admin/routing-rules', icon: Network })
    items.push({ label: 'SLA policies', path: '/admin/sla-policies', icon: Settings2 })
  }
  items.push({ label: 'Notifications', path: '/notifications', icon: Bell })
  items.push({ label: 'Profile', path: '/profile', icon: UserRound })
  return items
}

function canAccessNetwork(user: AuthUser) {
  return user.role === 'ADMIN' || (user.role === 'TECHNICAL_STAFF' && ['network', 'it support'].includes(user.technical_specialization.trim().toLowerCase()))
}

function networkRolesFor(user: AuthUser) {
  return new Set<AuthUser['role']>(canAccessNetwork(user) ? ['TECHNICAL_STAFF', 'ADMIN'] : [])
}

export default function App() {
  const queryClient = useQueryClient()
  const auth = useQuery({ queryKey: ['current-user'], queryFn: () => apiRequest<AuthUser>('/auth/me/'), retry: false, staleTime: 60_000 })
  const location = useLocation()

  useEffect(() => {
    const expireSession = () => {
      queryClient.clear()
      queryClient.setQueryData<AuthUser | null>(['current-user'], null)
    }
    window.addEventListener('campus:session-expired', expireSession)
    return () => window.removeEventListener('campus:session-expired', expireSession)
  }, [queryClient])

  if (!auth.data && location.pathname === '/') return <LandingPageRoute />
  if (auth.isPending) return <main className="full-state"><Loading label="Checking your session" /></main>
  if (auth.isError && !(auth.error instanceof ApiError && [401, 403].includes(auth.error.status))) {
    return <main className="full-state"><ErrorState title="Campus Operations could not connect" detail="Check that the API is running, then reload this page." /></main>
  }
  if (!auth.data) return <Routes><Route path="/" element={<LandingPageRoute />} /><Route path="/login" element={<LoginPage />} /><Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname }} />} /></Routes>
  return <AuthenticatedApp user={auth.data} />
}

function AuthenticatedApp({ user }: { user: AuthUser }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const location = useLocation()
  const notificationPreview = useQuery({
    queryKey: ['notifications', 1],
    queryFn: () => apiRequest<Paginated<NotificationRecord>>('/notifications/?page=1'),
    staleTime: 30_000,
  })
  const logout = useMutation({
    mutationFn: () => apiRequest<void>('/auth/logout/', { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: () => {
      queryClient.clear()
      navigate('/login', { replace: true })
    },
  })
  const page = pageFor(location.pathname, user.role)
  const navigation = navigationFor(user)
  const initials = user.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
  const hasUnreadNotifications = notificationPreview.data?.results.some((item) => !item.read_at) ?? false
  const isLocalWorkspace = ['localhost', '127.0.0.1'].includes(window.location.hostname)
  const activeBreadcrumb = location.pathname === '/dashboard' ? 'Dashboard' : page.title

  useEffect(() => {
    if (!menuOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        document.getElementById('navigation-toggle')?.focus()
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [menuOpen])

  return <div className="app-shell">
    {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <aside id="main-sidebar" className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}>
      <Link to="/dashboard" className="brand"><div className="brand-mark" aria-hidden="true">C</div><div><strong>Campus Operations</strong><span>Service platform</span></div></Link>
      <nav aria-label="Main navigation" className="nav-list">
        <div className="nav-group"><div className="nav-label">CAMPUS OPERATIONS</div>{navigation.filter((item) => ['/dashboard', '/issues', '/issues/new'].includes(item.path)).map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><item.icon className="nav-icon" size={17} aria-hidden="true" />{item.label}</NavLink>)}</div>
        {navigation.some((item) => item.path === '/assets') && <div className="nav-group"><div className="nav-label">CAMPUS RESOURCES</div>{navigation.filter((item) => item.path === '/assets').map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><item.icon className="nav-icon" size={17} aria-hidden="true" />{item.label}</NavLink>)}</div>}
        {navigation.some((item) => item.path === '/work-orders') && <div className="nav-group"><div className="nav-label">FIELD OPERATIONS</div>{navigation.filter((item) => item.path === '/work-orders').map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><item.icon className="nav-icon" size={17} aria-hidden="true" />{item.label}</NavLink>)}</div>}
        {navigation.some((item) => item.path.startsWith('/network/') || item.path === '/network-quality') && <div className="nav-group"><div className="nav-label">NETWORK FOUNDATION</div>{navigation.filter((item) => item.path.startsWith('/network/') || item.path === '/network-quality').map((item) => <NavLink key={item.path} to={item.path} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><item.icon className="nav-icon" size={17} aria-hidden="true" />{item.label}</NavLink>)}</div>}
        {navigation.some((item) => ['/admin', '/admin/routing-rules', '/admin/sla-policies'].includes(item.path)) && <div className="nav-group"><div className="nav-label">ADMINISTRATION</div>{navigation.filter((item) => ['/admin', '/admin/routing-rules', '/admin/sla-policies'].includes(item.path)).map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><item.icon className="nav-icon" size={17} aria-hidden="true" />{item.label}</NavLink>)}</div>}
        <div className="nav-group nav-group--account"><div className="nav-label">ACCOUNT</div>{navigation.filter((item) => ['/notifications', '/profile'].includes(item.path)).map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><item.icon className="nav-icon" size={17} aria-hidden="true" />{item.label}</NavLink>)}</div>
      </nav>
      <div className="sidebar-foot"><span className="environment-dot" />Project workspace<br /><small>Academic development environment</small></div>
      <div className="profile"><span className="avatar" aria-hidden="true">{initials}</span><span className="profile-copy"><strong>{user.full_name}</strong><small>{user.role.replace(/_/g, ' ')}</small></span></div>
    </aside>
    <div className="main-column">
      <header className="topbar">
        <div className="topbar-left"><Button id="navigation-toggle" className="menu-button" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="main-sidebar" onClick={() => setMenuOpen((open) => !open)}><Menu size={18} aria-hidden="true" /></Button><nav className="topbar-breadcrumb" aria-label="Breadcrumb"><Link to="/dashboard">Workspace</Link><span className="breadcrumb-context-separator" aria-hidden="true">/</span><Link className="breadcrumb-context" to="/dashboard">Campus Service Workspace</Link><span className="breadcrumb-current-separator" aria-hidden="true">/</span><span className="breadcrumb-current" aria-current="page">{activeBreadcrumb}</span></nav></div>
        <div className="topbar-actions"><span className="environment-pill">{isLocalWorkspace ? `${window.location.host} | Dev Workspace` : 'Workspace'}</span><Link to="/notifications" className="notification-bell" aria-label={hasUnreadNotifications ? 'Notifications, unread alerts' : 'Notifications'}><Bell size={17} aria-hidden="true" />{hasUnreadNotifications && <span className="notification-unread-dot" aria-hidden="true" />}</Link><Link to="/profile" className="top-user" aria-label={`Profile: ${user.full_name}, ${user.role.replace(/_/g, ' ')}`}><span className="top-avatar" aria-hidden="true">{initials}</span><span className="top-user-copy"><strong>{user.full_name}</strong><small>{user.role.replace(/_/g, ' ')}</small></span></Link><Button className="top-signout" onClick={() => logout.mutate()} disabled={logout.isPending}><LogOut size={15} aria-hidden="true" />{logout.isPending ? 'Signing out…' : 'Sign Out'}</Button></div>
      </header>
      <main className="content">
        <div className="page-heading"><div><div className="eyebrow">CAMPUS SERVICE WORKSPACE</div><h1>{page.title}</h1><p>{page.description}</p></div>{page.action && <Link className="button button--primary" to={page.action.path}>{page.action.label}</Link>}</div>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage user={user} />} />
          <Route path="/issues" element={<IssueListPage user={user} />} />
          <Route path="/issues/new" element={<IssueCreatePage user={user} />} />
          <Route path="/issues/:id" element={<IssueDetailPage user={user} />} />
          <Route path="/profile" element={<ProfilePage user={user} />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/login" element={<Navigate to="/dashboard" replace />} />
          <Route path="/network" element={<Navigate to="/dashboard" replace />} />
          <Route path="/network/coverage" element={<Navigate to="/dashboard" replace />} />
          <Route path="/work-orders" element={<RoleGate allowed={workOrderRoles} role={user.role}><WorkOrderListPage user={user} /></RoleGate>} />
          <Route path="/work-orders/:id" element={<RoleGate allowed={workOrderRoles} role={user.role}><WorkOrderDetailPage user={user} /></RoleGate>} />
          <Route path="/network/devices" element={<RoleGate allowed={networkRolesFor(user)} role={user.role}><NetworkDevicesPage canManage={networkManagementRoles.has(user.role)} /></RoleGate>} />
          <Route path="/network/devices/:id" element={<RoleGate allowed={networkRolesFor(user)} role={user.role}><NetworkDeviceDetailPage /></RoleGate>} />
          <Route path="/network/networks" element={<RoleGate allowed={networkRolesFor(user)} role={user.role}><NetworksPage canManage={networkManagementRoles.has(user.role)} /></RoleGate>} />
          <Route path="/network/measurements/:id" element={<RoleGate allowed={networkRolesFor(user)} role={user.role}><NetworkMeasurementEvaluationPage user={user} /></RoleGate>} />
          <Route path="/network/measurements" element={<RoleGate allowed={networkRolesFor(user)} role={user.role}><NetworkMeasurementsPage /></RoleGate>} />
          <Route path="/network-quality" element={<RoleGate allowed={networkRolesFor(user)} role={user.role}><NetworkQualityPage /></RoleGate>} />
          <Route path="/assets" element={<RoleGate allowed={assetRoles} role={user.role}><AssetsPage /></RoleGate>} />
          <Route path="/analytics" element={<Navigate to="/dashboard" replace />} />
          <Route path="/reports" element={<Navigate to="/dashboard" replace />} />
          <Route path="/admin" element={<RoleGate allowed={adminRoles} role={user.role}><AdminHome /></RoleGate>} />
          <Route path="/admin/routing-rules" element={<RoleGate allowed={adminRoles} role={user.role}><RoutingRulesPage /></RoleGate>} />
          <Route path="/admin/sla-policies" element={<RoleGate allowed={adminRoles} role={user.role}><SlaPoliciesPage /></RoleGate>} />
          <Route path="*" element={<PageContent title="Page not found" detail="Choose a section from the navigation." />} />
        </Routes>
        <footer className="footer">Campus Operations <span>•</span> Academic project workspace · Not an official LPU service</footer>
      </main>
    </div>
  </div>
}

function pageFor(path: string, role: AuthUser['role']) {
  if (path === '/dashboard' || path === '/') {
    const titles: Record<AuthUser['role'], string> = {
      STUDENT: 'My requests', STAFF: 'My service requests', TECHNICAL_STAFF: 'Technical staff workspace', ADMIN: 'Campus administration',
    }
    return { title: titles[role], description: 'A current view of issues visible to your account.' }
  }
  if (path === '/issues/new') return { title: 'Report an issue', description: 'Share what needs attention and where it is happening.' }
  if (path === '/issues') return { title: 'Issues', description: 'Review reports visible to your account.' , action: { label: '＋ Report an issue', path: '/issues/new' } }
  if (/^\/issues\/[^/]+$/.test(path)) return { title: 'Issue details', description: 'Review the report and its recorded status history.' }
  if (path === '/profile') return { title: 'Your profile', description: 'Review the account currently signed in.' }
  if (path === '/notifications') return { title: 'Notifications', description: 'Review internal updates relevant to your account.' }
  if (path === '/network/devices') return { title: 'Network devices', description: 'Campus access points, switches, routers, and gateways.' }
  if (/^\/network\/devices\/[^/]+$/.test(path)) return { title: 'Network device detail', description: 'Review the registered device and its raw measurement records.' }
  if (path === '/network/networks') return { title: 'Networks', description: 'Campus Wi-Fi, LAN, and WAN inventory.' }
  if (path === '/network/measurements') return { title: 'Measurements', description: 'Record and review raw network observations.' }
  if (path === '/network-quality') return { title: 'Network Quality', description: 'Network quality measurements and operational analysis.' }
  if (/^\/network\/measurements\/[^/]+$/.test(path)) return { title: 'Measurement evaluation', description: 'Review the transparent quality classification of one raw network measurement.' }
  if (path === '/work-orders') return { title: 'Work orders', description: 'Field work and maintenance coordination.' }
  if (/^\/work-orders\/[^/]+$/.test(path)) return { title: 'Work-order details', description: 'Coordinate field work, evidence, and supervisor verification.' }
  if (path === '/assets') return { title: 'Assets', description: 'Registered equipment and its campus location.' }
  if (path === '/admin') return { title: 'Administration', description: 'Review users, campus issues, priority requests, assignments, SLAs, work orders and network operations.' }
  if (path === '/admin/routing-rules') return { title: 'Routing rules', description: 'Configure how issue categories, locations, and priority route to operational teams.' }
  if (path === '/admin/sla-policies') return { title: 'SLA policies', description: 'Set response, resolution, warning, and escalation targets.' }
  return { title: 'Campus Operations', description: 'Campus issue management workspace.' }
}

function ProfilePage({ user }: { user: AuthUser }) {
  return <section className="profile-card"><div className="profile-large-avatar" aria-hidden="true">{user.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</div><div><h2>{user.full_name}</h2><p>{user.role.replace(/_/g, ' ')}</p></div><dl>{user.institutional_id && <div><dt>Institutional ID</dt><dd>{user.institutional_id}</dd></div>}{user.technical_specialization && <div><dt>Specialization</dt><dd>{user.technical_specialization}</dd></div>}<div><dt>Email</dt><dd>{user.email}</dd></div><div><dt>Phone</dt><dd>{user.phone_number || 'Not provided'}</dd></div><div><dt>Member since</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(user.date_joined))}</dd></div></dl></section>
}

function RoleGate({ allowed, role, children }: { allowed: Set<AuthUser['role']>; role: AuthUser['role']; children: ReactNode }) {
  if (!allowed.has(role)) return <PageContent title="Access restricted" detail="Your account does not have access to this section." />
  return children
}

function AdminHome() {
  const users = useQuery({ queryKey: ['admin-user-summary'], queryFn: () => apiRequest<{ user_counts: Record<string, number>; technical_staff: { id: number; full_name: string; institutional_id: string | null; technical_specialization: string; teams: string[]; is_active: boolean }[] }>('/auth/admin/summary/') })
  const issues = useQuery({ queryKey: ['admin-issue-summary'], queryFn: () => apiRequest<{ open: number; assigned: number; at_risk: number; breached: number; unassigned: number; priority_requests: number; automatically_assigned: number }>('/issues/summary/') })
  return <div className="admin-overview">
    {users.isPending || issues.isPending ? <div className="state-panel"><Loading label="Loading campus operations summary" /></div>
      : users.isError || issues.isError ? <ErrorState title="Administration summary could not be loaded" detail="Try again after checking the API connection." onRetry={() => { void users.refetch(); void issues.refetch() }} />
        : <>
          <section className="metric-grid" aria-label="Users by role">{Object.entries(users.data.user_counts).map(([role, count]) => <div className="metric-card" key={role}><span>{role.replace(/_/g, ' ')}</span><strong>{count}</strong></div>)}</section>
          <section className="metric-grid" aria-label="Campus issue operations"><Link to="/issues?unassigned=true" className="metric-card"><span>Unassigned issues</span><strong>{issues.data.unassigned}</strong></Link><Link to="/issues?priority_requested=true" className="metric-card"><span>Staff priority requests</span><strong>{issues.data.priority_requests}</strong></Link><Link to="/issues?automatically_assigned=true" className="metric-card"><span>Automatically assigned</span><strong>{issues.data.automatically_assigned}</strong></Link><div className="metric-card"><span>SLA warnings / breaches</span><strong>{issues.data.at_risk} / {issues.data.breached}</strong></div></section>
          <section className="panel"><h2>Technical staff and specializations</h2>{users.data.technical_staff.length ? <div className="table-scroll"><table className="issue-table"><thead><tr><th>Name</th><th>Employee ID</th><th>Specialization</th><th>Teams</th><th>Status</th></tr></thead><tbody>{users.data.technical_staff.map((member) => <tr key={member.id}><td>{member.full_name}</td><td>{member.institutional_id ?? 'Not configured'}</td><td>{member.technical_specialization || 'Not configured'}</td><td>{member.teams.join(', ') || 'No team'}</td><td>{member.is_active ? 'Active' : 'Inactive'}</td></tr>)}</tbody></table></div> : <EmptyState title="No technical staff accounts" detail="Add technical employees through the account administration page." />}</section>
        </>}
    <div className="admin-shortcuts"><Link className="panel" to="/issues"><h2>All campus issues</h2><p>Review priority requests, assignment history, status, and SLA events.</p></Link><Link className="panel" to="/work-orders"><h2>Work orders</h2><p>Assign and verify field work.</p></Link><Link className="panel" to="/network-quality"><h2>Network management and analytics</h2><p>Review network inventory, measurements, and quality trends.</p></Link><Link className="panel" to="/admin/routing-rules"><h2>Routing rules</h2><p>Configure category, location and priority routing to teams.</p></Link><Link className="panel" to="/admin/sla-policies"><h2>SLA policies</h2><p>Manage response, resolution and escalation thresholds.</p></Link><a className="panel" href={adminUrl}><h2>Reference data and accounts</h2><p>Manage campus locations, teams, and individual accounts.</p></a></div>
  </div>
}

function PageContent({ title, detail, link }: { title: string; detail: string; link?: { label: string; href: string } }) {
  return <section className="single-panel"><EmptyState title={title} detail={detail} />{link && <a className="button button--primary" href={link.href}>{link.label}</a>}</section>
}
