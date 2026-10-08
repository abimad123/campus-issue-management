import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '../../lib/api'
import type { IssueRecord, Paginated, AuthUser } from '../../types/api'
import { Badge, EmptyState, ErrorState, Loading } from '../../components/ui'

type Summary = { open: number; assigned: number; at_risk: number; breached: number; unassigned: number }
type DashboardData = { all: Paginated<IssueRecord>; open: Paginated<IssueRecord>; resolved: Paginated<IssueRecord>; summary: Summary | null }

const operationalRoles = new Set<AuthUser['role']>(['TECHNICIAN', 'SUPERVISOR', 'FACILITY_MANAGER', 'IT_MANAGER', 'DEPARTMENT_HEAD', 'CAMPUS_ADMIN', 'SYSTEM_ADMIN'])
const studentRoles = new Set<AuthUser['role']>(['STUDENT', 'STAFF'])

function workspaceFor(role: AuthUser['role']) {
  switch (role) {
    case 'STUDENT': return { eyebrow: 'STUDENT SERVICES', title: 'Your campus requests', detail: 'Report an issue and follow its progress from one place.', queue: 'Recent requests' }
    case 'STAFF': return { eyebrow: 'STAFF SERVICES', title: 'Your service requests', detail: 'Track reports you have submitted and raise a new campus request.', queue: 'Recent requests' }
    case 'TECHNICIAN': return { eyebrow: 'FIELD OPERATIONS', title: 'Technician workspace', detail: 'Review issues in your assignment scope and keep their status current.', queue: 'Issue queue' }
    case 'SUPERVISOR': return { eyebrow: 'TEAM OPERATIONS', title: 'Team supervisor workspace', detail: 'Review visible team issues, assignment coverage, and SLA attention areas.', queue: 'Team issue queue' }
    case 'FACILITY_MANAGER': return { eyebrow: 'FACILITIES', title: 'Facilities operations', detail: 'Review service issues visible to your operational scope.', queue: 'Facilities issue queue' }
    case 'IT_MANAGER': return { eyebrow: 'INFORMATION TECHNOLOGY', title: 'IT operations', detail: 'Review technology and network-related service issues visible to your scope.', queue: 'IT issue queue' }
    case 'DEPARTMENT_HEAD': return { eyebrow: 'DEPARTMENT OPERATIONS', title: 'Department overview', detail: 'Review issue activity available to your department-level account.', queue: 'Recent issues' }
    case 'CAMPUS_ADMIN': return { eyebrow: 'CAMPUS OPERATIONS', title: 'Campus service overview', detail: 'Review campus issue volume, assignment coverage, and SLA attention.', queue: 'Campus issue register' }
    default: return { eyebrow: 'PLATFORM ADMINISTRATION', title: 'System operations', detail: 'Review service activity and manage platform workflow configuration.', queue: 'Visible issue register' }
  }
}

export default function DashboardPage({ user }: { user: AuthUser }) {
  const workspace = workspaceFor(user.role)
  const isOperational = operationalRoles.has(user.role)
  const dashboard = useQuery({
    queryFn: async (): Promise<DashboardData> => {
      const [all, open, resolved] = await Promise.all([
        apiRequest<Paginated<IssueRecord>>('/issues/'),
        apiRequest<Paginated<IssueRecord>>('/issues/?status=OPEN'),
        apiRequest<Paginated<IssueRecord>>('/issues/?status=RESOLVED'),
      ])
      const summary = isOperational ? await apiRequest<Summary>('/issues/summary/') : null
      return { all, open, resolved, summary }
    },
    queryKey: ['dashboard-issues', user.role],
  })

  return <div className="workspace-dashboard">
    <section className="workspace-intro">
      <div><p className="eyebrow">{workspace.eyebrow}</p><h2>{workspace.title}</h2><p>{workspace.detail}</p></div>
      <Link className="button button--primary" to={studentRoles.has(user.role) ? '/issues/new' : '/issues'}>{studentRoles.has(user.role) ? '＋ Report an issue' : 'Open issue register'}</Link>
    </section>

    {dashboard.isPending ? <div className="state-panel"><Loading label="Loading your workspace" /></div>
      : dashboard.isError ? <ErrorState title="Workspace data could not be loaded" detail="Check your connection and try again." />
        : <>
          <section className={`metric-grid workspace-metrics ${isOperational ? '' : 'workspace-metrics--reporter'}`} aria-label="Issue summary">
            {dashboard.data.summary ? <>
              <Metric label="Open" value={dashboard.data.summary.open} />
              <Metric label="Assigned" value={dashboard.data.summary.assigned} />
              <Metric label="Unassigned" value={dashboard.data.summary.unassigned} />
              <Metric label="SLA at risk" value={dashboard.data.summary.at_risk} tone="warning" />
              <Metric label="SLA breached" value={dashboard.data.summary.breached} tone="danger" />
            </> : <>
              <Metric label="Requests submitted" value={dashboard.data.all.count} />
              <Metric label="Open requests" value={dashboard.data.open.count} />
              <Metric label="Resolved requests" value={dashboard.data.resolved.count} tone="positive" />
            </>}
          </section>

          <section className="queue-section" aria-labelledby="queue-title">
            <div className="queue-heading"><div><p className="eyebrow">CURRENT RECORDS</p><h2 id="queue-title">{workspace.queue}</h2><p>Based on issues visible to your account.</p></div><Link className="text-link" to="/issues">View issue register <span aria-hidden="true">→</span></Link></div>
            {dashboard.data.all.results.length === 0 ? <div className="queue-empty"><EmptyState title={studentRoles.has(user.role) ? 'No requests yet' : 'No visible issues'} detail={studentRoles.has(user.role) ? 'When you submit a campus request, its status and updates will appear here.' : 'There are no issues in your current visibility scope.'} />{studentRoles.has(user.role) && <Link className="button button--primary" to="/issues/new">Report your first issue</Link>}</div>
              : <div className="table-scroll"><table className="issue-table workspace-table"><thead><tr><th scope="col">Ticket</th><th scope="col">Issue</th><th scope="col">Category</th><th scope="col">Location</th>{isOperational && <><th scope="col">Priority</th><th scope="col">Team</th></>}<th scope="col">Status</th><th scope="col">Updated</th></tr></thead><tbody>
                {dashboard.data.all.results.slice(0, 8).map((issue) => <tr key={issue.id}>
                  <td><Link className="ticket-link" to={`/issues/${issue.id}`}>{issue.ticket_number}</Link></td>
                  <td><Link className="issue-title-link" to={`/issues/${issue.id}`}>{issue.title}</Link></td>
                  <td>{issue.category.name}</td><td>{issue.location_name}</td>
                  {isOperational && <><td><Badge tone={issue.priority === 'HIGH' || issue.priority === 'CRITICAL' ? 'red' : issue.priority === 'LOW' ? 'neutral' : 'blue'}>{issue.priority}</Badge></td><td>{issue.assigned_team_name ?? 'Unassigned'}</td></>}
                  <td><Badge tone={issue.status === 'RESOLVED' || issue.status === 'CLOSED' ? 'green' : issue.status === 'REOPENED' ? 'red' : 'blue'}>{issue.status.replace(/_/g, ' ')}</Badge></td>
                  <td className="date-cell">{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(issue.updated_at))}</td>
                </tr>)}
              </tbody></table></div>}
          </section>
        </>}
  </div>
}

function Metric({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'positive' | 'warning' | 'danger' }) {
  return <article className={`workspace-metric workspace-metric--${tone}`}><div>{label}</div><strong>{value.toLocaleString()}</strong></article>
}
