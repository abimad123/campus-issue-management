import { useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Badge, Button, EmptyState } from './components/ui'

const navigation = [
  { label: 'Dashboard', path: '/dashboard', icon: '▦' },
  { label: 'Issues', path: '/issues', icon: '◷' },
  { label: 'Work Orders', path: '/work-orders', icon: '☷' },
  { label: 'Network Quality', path: '/network', icon: '⌁' },
  { label: 'Assets', path: '/assets', icon: '◇' },
  { label: 'Analytics', path: '/analytics', icon: '▤' },
  { label: 'Reports', path: '/reports', icon: '▧' },
  { label: 'Administration', path: '/admin', icon: '⚙' },
]

const pages: Record<string, { title: string; description: string; action?: string }> = {
  '/issues': { title: 'Issues', description: 'Review campus reports and service requests.', action: 'New issue' },
  '/work-orders': { title: 'Work orders', description: 'Coordinate field work and maintenance activity.' },
  '/network': { title: 'Network quality', description: 'Review campus connectivity measurement tools.' },
  '/network/coverage': { title: 'Coverage', description: 'Explore network measurements by campus zone.' },
  '/assets': { title: 'Assets', description: 'Maintain a shared inventory of campus equipment.' },
  '/analytics': { title: 'Analytics', description: 'Operational measures will appear when connected to real records.' },
  '/reports': { title: 'Reports', description: 'Prepare operational reports from verified platform data.' },
  '/admin': { title: 'Administration', description: 'Configure platform access and operational settings.' },
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const isDashboard = location.pathname === '/dashboard'
  const page = isDashboard ? { title: 'Campus overview', description: 'A clear view of service activity across campus.' } : pages[location.pathname] ?? { title: 'Issue details', description: 'Issue records will be available after the service workflow is connected.' }

  return <div className="app-shell">
    {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}>
      <div className="brand"><div className="brand-mark">C</div><div><strong>Campus Operations</strong><span>Service platform</span></div></div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="nav-list">
        {navigation.map((item) => <NavLink key={item.path} to={item.path} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</NavLink>)}
      </nav>
      <div className="sidebar-foot"><span className="environment-dot" />Foundation workspace<br /><small>Academic project environment</small></div>
      <div className="profile">
        <span className="avatar">OP</span><span className="profile-copy"><strong>Operations team</strong><small>Project workspace</small></span><span className="profile-more">···</span>
      </div>
    </aside>
    <div className="main-column">
      <header className="topbar">
        <div className="topbar-left"><Button className="menu-button" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>☰</Button><span className="breadcrumb">Workspace <span>/</span> {page.title}</span></div>
        <div className="topbar-actions"><Badge tone="blue">Development</Badge><Button className="notification-button" aria-label="Notifications are not available in Phase 1" title="Notifications are not available in Phase 1" disabled>♧<i /></Button><span className="top-avatar"><span className="sr-only">Operations team</span><span aria-hidden="true">OP</span></span></div>
      </header>
      <main className="content">
        <div className="page-heading"><div><div className="eyebrow">LOVELY PROFESSIONAL UNIVERSITY · PROJECT WORKSPACE</div><h1>{page.title}</h1><p>{page.description}</p></div>{page.action && <Button variant="primary" disabled title="Issue intake is not available in Phase 1">＋ {page.action}</Button>}</div>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/issues" element={<PageContent title="No issues to display" detail="Issue records will appear here once the backend workflow is implemented." />} />
          <Route path="/issues/:id" element={<PageContent title="Issue record unavailable" detail="Issue details will be shown after issue records are connected." />} />
          <Route path="/work-orders" element={<PageContent title="No work orders yet" detail="Assigned field work will appear here when work order management is implemented." />} />
          <Route path="/network" element={<PageContent title="Measurements not connected" detail="Network test collection is planned for a later project phase." />} />
          <Route path="/network/coverage" element={<PageContent title="Coverage data unavailable" detail="Zone coverage will be shown when real network measurements are available." />} />
          <Route path="/assets" element={<PageContent title="Asset inventory is empty" detail="Campus assets will appear here after inventory management is implemented." />} />
          <Route path="/analytics" element={<PageContent title="No analytics available" detail="This workspace does not contain operational records yet." />} />
          <Route path="/reports" element={<PageContent title="No reports available" detail="Reports will be generated from verified platform data." />} />
          <Route path="/admin" element={<PageContent title="Administration setup" detail="Access controls and operational configuration have not been configured yet." />} />
          <Route path="*" element={<PageContent title="Page not found" detail="Choose a section from the navigation." />} />
        </Routes>
        <footer className="footer">Campus Operations <span>•</span> Academic project workspace</footer>
      </main>
    </div>
  </div>
}

function Dashboard() {
  const metrics = ['Open issues', 'SLA at risk', 'SLA breached', 'Work orders', 'Network health']
  return <>
    <section className="metric-grid" aria-label="Operational metrics">
      {metrics.map((metric) => <article className="metric-card" key={metric}><div className="metric-top"><span>{metric}</span><span className="metric-icon" aria-hidden="true">↗</span></div><div className="metric-value">—</div><div className="metric-note">Awaiting connected data</div></article>)}
    </section>
    <section className="dashboard-grid">
      <Panel title="Recent issues" detail="Latest reports submitted across campus" wide><EmptyState title="No issue activity" detail="New reports will appear here when the issue intake workflow is available." /></Panel>
      <Panel title="Team workload" detail="Active assignments by team"><EmptyState title="No assignments" detail="Workload will be based on current assignments." /></Panel>
      <Panel title="Network health" detail="Recent measurement summary"><EmptyState title="No measurements" detail="Network health requires collected measurement data." /></Panel>
      <Panel title="Issue trends" detail="Reports over time"><EmptyState title="No trend data" detail="Trends will appear when issue records are available." /></Panel>
    </section>
  </>
}

function Panel({ title, detail, children, wide = false }: { title: string; detail: string; children: ReactNode; wide?: boolean }) {
  return <section className={`panel ${wide ? 'panel--wide' : ''}`}><div className="panel-heading"><div><h2>{title}</h2><p>{detail}</p></div><button className="more-button" aria-label={`More options for ${title} are not available yet`} title="Actions are not available in Phase 1" disabled>···</button></div>{children}</section>
}

function PageContent({ title, detail }: { title: string; detail: string }) {
  return <section className="single-panel"><EmptyState title={title} detail={detail} /></section>
}

export default App
