import { Link } from 'react-router-dom'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiRequest } from '../../lib/api'
import type { IssueRecord, Paginated, AuthUser, WorkOrderRecord } from '../../types/api'
import type { WorkOrderSummary } from '../workorders/WorkOrderPages'
import { Badge, EmptyState, ErrorState, Loading } from '../../components/ui'

type Summary = { open: number; assigned: number; at_risk: number; breached: number; unassigned: number }
type DashboardData = { all: Paginated<IssueRecord>; open: Paginated<IssueRecord>; resolved: Paginated<IssueRecord>; summary: Summary | null }

const operationalRoles = new Set<AuthUser['role']>(['TECHNICIAN', 'SUPERVISOR', 'FACILITY_MANAGER', 'IT_MANAGER', 'DEPARTMENT_HEAD', 'CAMPUS_ADMIN', 'SYSTEM_ADMIN'])
const studentRoles = new Set<AuthUser['role']>(['STUDENT', 'STAFF'])

function workspaceFor(role: AuthUser['role']) {
  switch (role) {
    case 'STUDENT': return { eyebrow: 'STUDENT SERVICES', title: 'Your campus requests', detail: 'Report an issue and follow its progress from one place.', queue: 'Recent requests' }
    case 'STAFF': return { eyebrow: 'STAFF SERVICES', title: 'Your service requests', detail: 'Track reports you have submitted and raise a new campus request.', queue: 'Recent requests' }
    case 'TECHNICIAN': return { eyebrow: 'FIELD OPERATIONS', title: 'Technician workspace', detail: 'Review assigned field tasks, record progress, and submit completed work for verification.', queue: 'Visible issues' }
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
  const workOrderSummary = useQuery({ queryKey: ['work-order-summary'], queryFn: () => apiRequest<WorkOrderSummary>('/work-orders/summary/'), enabled: isOperational })
  const workOrderQueue = useQuery({
    queryKey: ['dashboard-work-orders', user.role],
    queryFn: () => apiRequest<Paginated<WorkOrderRecord>>(`/work-orders/${user.role === 'SUPERVISOR' ? '?status=COMPLETED' : ''}`),
    enabled: user.role === 'TECHNICIAN' || user.role === 'SUPERVISOR',
  })

  return <div className="workspace-dashboard">
    <section className="workspace-intro">
      <div><p className="eyebrow">{workspace.eyebrow}</p><h2>{workspace.title}</h2><p>{workspace.detail}</p></div>
      <Link className="button button--primary" to={studentRoles.has(user.role) ? '/issues/new' : '/issues'}>{studentRoles.has(user.role) ? '＋ Report an issue' : 'Open issue register'}</Link>
    </section>

    {dashboard.isPending ? <div className="state-panel"><Loading label="Loading your workspace" /></div>
      : dashboard.isError ? <ErrorState title="Workspace data could not be loaded" detail="Check your connection and try again." onRetry={() => { void dashboard.refetch() }} />
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
          {(user.role === 'TECHNICIAN' || user.role === 'SUPERVISOR') && <WorkOrderQueue role={user.role} query={workOrderQueue} />}
          {isOperational && <section className="queue-section work-order-dashboard-block" aria-labelledby="work-order-summary-title"><div className="queue-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h2 id="work-order-summary-title">Work-order status</h2><p>Counts from work orders visible to your account.</p></div><Link className="text-link" to="/work-orders">Open work orders <span aria-hidden="true">→</span></Link></div>
            {workOrderSummary.isPending ? <div className="state-panel"><Loading label="Loading work-order summary" /></div> : workOrderSummary.isError ? <ErrorState title="Work-order summary unavailable" detail="Operational work-order metrics could not be loaded." onRetry={() => { void workOrderSummary.refetch() }} /> : <div className="work-order-metrics"><Metric label="Open" value={workOrderSummary.data.open} /><Metric label="In progress" value={workOrderSummary.data.in_progress} /><Metric label="Awaiting verification" value={workOrderSummary.data.awaiting_verification} /><Metric label="Verified / closed" value={workOrderSummary.data.verified} /></div>}
          </section>}
        </>}
  </div>
}

function WorkOrderQueue({ role, query }: { role: AuthUser['role']; query: UseQueryResult<Paginated<WorkOrderRecord>, Error> }) {
  const supervisor = role === 'SUPERVISOR'
  const heading = supervisor ? 'Awaiting supervisor review' : 'My assigned work orders'
  if (query.isPending) return <section className="queue-section" aria-labelledby="dashboard-work-orders-title"><div className="queue-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h2 id="dashboard-work-orders-title">{heading}</h2></div><Link className="text-link" to="/work-orders">Open work orders <span aria-hidden="true">→</span></Link></div><div className="state-panel"><Loading label="Loading work orders" /></div></section>
  return <section className="queue-section" aria-labelledby="dashboard-work-orders-title"><div className="queue-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h2 id="dashboard-work-orders-title">{heading}</h2><p>{supervisor ? 'Completed tasks awaiting an operational review.' : 'Tasks assigned to your technician account.'}</p></div><Link className="text-link" to="/work-orders">Open work orders <span aria-hidden="true">→</span></Link></div>
    {query.isError ? <ErrorState title="Work orders could not be loaded" detail="Your issue dashboard is still available. Try loading the work-order list again." onRetry={() => { void query.refetch() }} />
      : query.data.count === 0 ? <div className="queue-empty"><EmptyState title={supervisor ? 'No work orders awaiting review' : 'No work orders assigned'} detail={supervisor ? 'Completed technician work will appear here when it is ready for verification.' : 'Work orders assigned to your account will appear here.'} /></div>
        : <div className="table-scroll"><table className="issue-table workspace-table"><thead><tr><th scope="col">Work order</th><th scope="col">Issue</th><th scope="col">Team</th><th scope="col">Status</th></tr></thead><tbody>{query.data.results.slice(0, 5).map((workOrder) => <tr key={workOrder.id}><td><Link className="ticket-link" to={`/work-orders/${workOrder.id}`}>{workOrder.number}</Link><small className="table-subtitle">{workOrder.title}</small></td><td><Link className="issue-title-link" to={`/issues/${workOrder.issue}`}>{workOrder.issue_ticket_number} · {workOrder.issue_title}</Link></td><td>{workOrder.team_name}</td><td><Badge tone={workOrder.status === 'CLOSED' || workOrder.status === 'VERIFIED' ? 'green' : workOrder.status === 'REWORK' ? 'red' : 'blue'}>{workOrder.status.replace(/_/g, ' ')}</Badge></td></tr>)}</tbody></table></div>}
  </section>
}

function Metric({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'positive' | 'warning' | 'danger' }) {
  return <article className={`workspace-metric workspace-metric--${tone}`}><div>{label}</div><strong>{value.toLocaleString()}</strong></article>
}
