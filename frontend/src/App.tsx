import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Badge, Button, EmptyState, ErrorState, Loading } from './components/ui'
import AssetsPage from './features/assets/AssetsPage'
import { RoutingRulesPage, SlaPoliciesPage } from './features/admin/WorkflowConfigPages'
import DashboardPage from './features/issues/DashboardPage'
import { IssueCreatePage, IssueDetailPage, IssueListPage } from './features/issues/IssuePages'
import LoginPage from './features/auth/LoginPage'
import { ApiError, apiRequest } from './lib/api'
import type { AuthUser } from './types/api'

type NavigationItem = { label: string; path: string; icon: string; end?: boolean }
const adminRoles = new Set<AuthUser['role']>(['CAMPUS_ADMIN', 'SYSTEM_ADMIN'])
const assetRoles = new Set<AuthUser['role']>(['FACILITY_MANAGER', 'IT_MANAGER', 'CAMPUS_ADMIN', 'SYSTEM_ADMIN'])
const adminUrl = `${new URL(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api').origin}/admin/`

function navigationFor(user: AuthUser): NavigationItem[] {
  const items: NavigationItem[] = [
    { label: 'Dashboard', path: '/dashboard', icon: '▦', end: true },
    { label: user.role === 'STUDENT' || user.role === 'STAFF' ? 'My issues' : 'Issue register', path: '/issues', icon: '◷', end: true },
    { label: 'Report an issue', path: '/issues/new', icon: '＋' },
  ]
  if (assetRoles.has(user.role)) items.push({ label: 'Asset register', path: '/assets', icon: '◇' })
  if (adminRoles.has(user.role)) {
    items.push({ label: 'Administration', path: '/admin', icon: '⚙' })
    items.push({ label: 'Routing rules', path: '/admin/routing-rules', icon: '↗' })
    items.push({ label: 'SLA policies', path: '/admin/sla-policies', icon: '◷' })
  }
  items.push({ label: 'Profile', path: '/profile', icon: '○' })
  return items
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

  if (auth.isPending) return <main className="full-state"><Loading label="Checking your session" /></main>
  if (auth.isError && !(auth.error instanceof ApiError && [401, 403].includes(auth.error.status))) {
    return <main className="full-state"><ErrorState title="Campus Operations could not connect" detail="Check that the API is running, then reload this page." /></main>
  }
  if (!auth.data) return <Routes><Route path="/login" element={<LoginPage />} /><Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname }} />} /></Routes>
  return <AuthenticatedApp user={auth.data} />
}

function AuthenticatedApp({ user }: { user: AuthUser }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const location = useLocation()
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

  return <div className="app-shell">
    {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}>
      <Link to="/dashboard" className="brand"><div className="brand-mark" aria-hidden="true">C</div><div><strong>Campus Operations</strong><span>Service platform</span></div></Link>
      <nav aria-label="Main navigation" className="nav-list">
        <div className="nav-group"><div className="nav-label">CAMPUS OPERATIONS</div>{navigation.filter((item) => ['/dashboard', '/issues', '/issues/new'].includes(item.path)).map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</NavLink>)}</div>
        {navigation.some((item) => item.path === '/assets') && <div className="nav-group"><div className="nav-label">CAMPUS RESOURCES</div>{navigation.filter((item) => item.path === '/assets').map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</NavLink>)}</div>}
        {navigation.some((item) => ['/admin', '/admin/routing-rules', '/admin/sla-policies'].includes(item.path)) && <div className="nav-group"><div className="nav-label">ADMINISTRATION</div>{navigation.filter((item) => ['/admin', '/admin/routing-rules', '/admin/sla-policies'].includes(item.path)).map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</NavLink>)}</div>}
        <div className="nav-group nav-group--account"><div className="nav-label">ACCOUNT</div>{navigation.filter((item) => item.path === '/profile').map((item) => <NavLink key={item.path} to={item.path} end={item.end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</NavLink>)}</div>
      </nav>
      <div className="sidebar-foot"><span className="environment-dot" />Project workspace<br /><small>Academic development environment</small></div>
      <div className="profile"><span className="avatar" aria-hidden="true">{initials}</span><span className="profile-copy"><strong>{user.full_name}</strong><small>{user.role.replace(/_/g, ' ')}</small></span></div>
    </aside>
    <div className="main-column">
      <header className="topbar">
        <div className="topbar-left"><Button className="menu-button" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>☰</Button><span className="breadcrumb">Workspace <span>/</span> {page.title}</span></div>
        <div className="topbar-actions"><Badge tone="blue">Development</Badge><Link to="/profile" className="top-avatar" aria-label={`Profile: ${user.full_name}`}>{initials}</Link><Button onClick={() => logout.mutate()} disabled={logout.isPending}>{logout.isPending ? 'Signing out…' : 'Sign out'}</Button></div>
      </header>
      <main className="content">
        <div className="page-heading"><div><div className="eyebrow">CAMPUS SERVICE WORKSPACE</div><h1>{page.title}</h1><p>{page.description}</p></div>{page.action && <Link className="button button--primary" to={page.action.path}>{page.action.label}</Link>}</div>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage user={user} />} />
          <Route path="/issues" element={<IssueListPage user={user} />} />
          <Route path="/issues/new" element={<IssueCreatePage />} />
          <Route path="/issues/:id" element={<IssueDetailPage user={user} />} />
          <Route path="/profile" element={<ProfilePage user={user} />} />
          <Route path="/login" element={<Navigate to="/dashboard" replace />} />
          <Route path="/network" element={<Navigate to="/dashboard" replace />} />
          <Route path="/network/coverage" element={<Navigate to="/dashboard" replace />} />
          <Route path="/work-orders" element={<Navigate to="/issues" replace />} />
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
      STUDENT: 'My requests', STAFF: 'My service requests', TECHNICIAN: 'Field operations', SUPERVISOR: 'Team overview',
      FACILITY_MANAGER: 'Facilities overview', IT_MANAGER: 'IT operations', DEPARTMENT_HEAD: 'Department overview',
      CAMPUS_ADMIN: 'Campus operations', SYSTEM_ADMIN: 'Platform overview',
    }
    return { title: titles[role], description: 'A current view of issues visible to your account.' }
  }
  if (path === '/issues/new') return { title: 'Report an issue', description: 'Share what needs attention and where it is happening.' }
  if (path === '/issues') return { title: 'Issues', description: 'Review reports visible to your account.' , action: { label: '＋ Report an issue', path: '/issues/new' } }
  if (/^\/issues\/[^/]+$/.test(path)) return { title: 'Issue details', description: 'Review the report and its recorded status history.' }
  if (path === '/profile') return { title: 'Your profile', description: 'Review the account currently signed in.' }
  if (path.startsWith('/network')) return { title: 'Network quality', description: 'Campus network measurement tools.' }
  if (path === '/work-orders') return { title: 'Work orders', description: 'Field work and maintenance coordination.' }
  if (path === '/assets') return { title: 'Assets', description: 'Registered equipment and its campus location.' }
  if (path === '/admin') return { title: 'Administration', description: 'Development access to reference data and accounts.' }
  if (path === '/admin/routing-rules') return { title: 'Routing rules', description: 'Configure how issue categories, locations, and priority route to operational teams.' }
  if (path === '/admin/sla-policies') return { title: 'SLA policies', description: 'Set response, resolution, warning, and escalation targets.' }
  return { title: 'Campus Operations', description: 'Campus issue management workspace.' }
}

function ProfilePage({ user }: { user: AuthUser }) {
  return <section className="profile-card"><div className="profile-large-avatar" aria-hidden="true">{user.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</div><div><h2>{user.full_name}</h2><p>{user.role.replace(/_/g, ' ')}</p></div><dl><div><dt>Email</dt><dd>{user.email}</dd></div><div><dt>Phone</dt><dd>{user.phone_number || 'Not provided'}</dd></div><div><dt>Member since</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(user.date_joined))}</dd></div></dl></section>
}

function RoleGate({ allowed, role, children }: { allowed: Set<AuthUser['role']>; role: AuthUser['role']; children: ReactNode }) {
  if (!allowed.has(role)) return <PageContent title="Access restricted" detail="Your account does not have access to this section." />
  return children
}

function AdminHome() {
  return <div className="admin-shortcuts"><Link className="panel" to="/admin/routing-rules"><h2>Routing rules</h2><p>Configure category, location and priority routing to teams.</p></Link><Link className="panel" to="/admin/sla-policies"><h2>SLA policies</h2><p>Manage response, resolution and escalation thresholds.</p></Link><a className="panel" href={adminUrl}><h2>Reference data</h2><p>Manage accounts and campus reference records in Django Admin.</p></a></div>
}

function PageContent({ title, detail, link }: { title: string; detail: string; link?: { label: string; href: string } }) {
  return <section className="single-panel"><EmptyState title={title} detail={detail} />{link && <a className="button button--primary" href={link.href}>{link.label}</a>}</section>
}
