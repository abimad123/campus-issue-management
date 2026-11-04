import { Link } from 'react-router-dom'
import { ArrowRight, BadgeCheck, CircleAlert, ClipboardList, Clock3, Signal } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiRequest } from '../../lib/api'
import type { IssueRecord, Paginated, AuthUser, WorkOrderRecord, NetworkAnalyticsSummary } from '../../types/api'
import type { WorkOrderSummary } from '../workorders/WorkOrderPages'
import { Badge, EmptyState, ErrorState, Loading } from '../../components/ui'

type Summary = { open: number; assigned: number; at_risk: number; breached: number; unassigned: number }
type DashboardData = { all: Paginated<IssueRecord>; open: Paginated<IssueRecord>; resolved: Paginated<IssueRecord>; summary: Summary | null }

const operationalRoles = new Set<AuthUser['role']>(['TECHNICAL_STAFF', 'ADMIN'])
const studentRoles = new Set<AuthUser['role']>(['STUDENT', 'STAFF'])

function workspaceFor(role: AuthUser['role']) {
  switch (role) {
    case 'STUDENT': return { eyebrow: 'STUDENT SERVICES', title: 'Student Service Desk', detail: 'Report a campus issue and follow its progress from one place.', queue: 'Recent requests' }
    case 'STAFF': return { eyebrow: 'STAFF SERVICES', title: 'Your service requests', detail: 'Track reports you have submitted and raise a new campus request.', queue: 'Recent requests' }
    case 'TECHNICAL_STAFF': return { eyebrow: 'FIELD OPERATIONS', title: 'Technical staff workspace', detail: 'Review assigned field tasks, record progress, and submit completed work for verification.', queue: 'Assigned issues' }
    default: return { eyebrow: 'CAMPUS OPERATIONS', title: 'Campus administration', detail: 'Review campus service issues, assignment coverage, priorities and SLA attention.', queue: 'Campus issue register' }
  }
}

export default function DashboardPage({ user }: { user: AuthUser }) {
  const workspace = workspaceFor(user.role)
  const isOperational = operationalRoles.has(user.role)
  const hasNetworkAccess = user.role === 'ADMIN' || (user.role === 'TECHNICAL_STAFF' && ['network', 'it support'].includes(user.technical_specialization.trim().toLowerCase()))
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
  const networkQuality = useQuery({
    queryKey: ['dashboard-network-quality'],
    queryFn: () => apiRequest<NetworkAnalyticsSummary>('/network-analytics/summary/'),
    enabled: hasNetworkAccess,
    staleTime: 60_000,
  })
  const workOrderSummary = useQuery({ queryKey: ['work-order-summary'], queryFn: () => apiRequest<WorkOrderSummary>('/work-orders/summary/'), enabled: isOperational })
  const workOrderQueue = useQuery({
    queryKey: ['dashboard-work-orders', user.role],
    queryFn: () => apiRequest<Paginated<WorkOrderRecord>>(`/work-orders/${user.role === 'ADMIN' ? '?status=COMPLETED' : ''}`),
    enabled: user.role === 'TECHNICAL_STAFF' || user.role === 'ADMIN',
  })

  return <div className="workspace-dashboard">
    <section className="workspace-intro">
      <div><p className="eyebrow">{workspace.eyebrow}</p><h2>{workspace.title}</h2><p>{workspace.detail}</p></div>
      <Link className="button button--primary" to={studentRoles.has(user.role) ? '/issues/new' : '/issues'}>{studentRoles.has(user.role) ? '+ Report New Issue' : 'Open issue register'}</Link>
    </section>

    {dashboard.isPending ? <div className="state-panel"><Loading label="Loading your workspace" /></div>
      : dashboard.isError ? <ErrorState title="Workspace data could not be loaded" detail="Check your connection and try again." onRetry={() => { void dashboard.refetch() }} />
        : <>
          <section className={`metric-grid workspace-metrics ${isOperational ? '' : 'workspace-metrics--reporter'}`} aria-label="Issue summary">
            {dashboard.data.summary ? <>
              <Metric label="Open" value={dashboard.data.summary.open} detail="Active issue records" icon={CircleAlert} />
              <Metric label="Assigned" value={dashboard.data.summary.assigned} detail="With a responsible team member" icon={BadgeCheck} />
              <Metric label="Unassigned" value={dashboard.data.summary.unassigned} detail="Needs an assignment" icon={CircleAlert} />
              <Metric label="SLA at risk" value={dashboard.data.summary.at_risk} detail="Approaching a stored deadline" tone="warning" icon={Clock3} />
              <Metric label="SLA breached" value={dashboard.data.summary.breached} detail="Recorded breach events" tone="danger" icon={Clock3} />
            </> : <>
              <Metric label="Total submitted" value={dashboard.data.all.count} detail="All time campus tickets" icon={ClipboardList} />
              <Metric label="Open requests" value={dashboard.data.open.count} detail="Currently in Open status" icon={CircleAlert} />
              <Metric label="Resolved requests" value={dashboard.data.resolved.count} detail="Marked resolved" tone="positive" icon={BadgeCheck} />
            </>}
            {hasNetworkAccess && <NetworkQualityMetric query={networkQuality} />}
          </section>

          <section className="queue-section" aria-labelledby="queue-title">
            <div className="queue-heading"><div><p className="eyebrow">CURRENT RECORDS</p><h2 id="queue-title">{workspace.queue}</h2><p>Based on issues visible to your account.</p></div><Link className="text-link" to="/issues">View issue register <ArrowRight size={15} aria-hidden="true" /></Link></div>
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
          {(user.role === 'TECHNICAL_STAFF' || user.role === 'ADMIN') && <WorkOrderQueue role={user.role} query={workOrderQueue} />}
          {isOperational && <section className="queue-section work-order-dashboard-block" aria-labelledby="work-order-summary-title"><div className="queue-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h2 id="work-order-summary-title">Work-order status</h2><p>Counts from work orders visible to your account.</p></div><Link className="text-link" to="/work-orders">Open work orders <span aria-hidden="true">→</span></Link></div>
            {workOrderSummary.isPending ? <div className="state-panel"><Loading label="Loading work-order summary" /></div> : workOrderSummary.isError ? <ErrorState title="Work-order summary unavailable" detail="Operational work-order metrics could not be loaded." onRetry={() => { void workOrderSummary.refetch() }} /> : <div className="work-order-metrics"><Metric label="Open" value={workOrderSummary.data.open} /><Metric label="In progress" value={workOrderSummary.data.in_progress} /><Metric label="Awaiting verification" value={workOrderSummary.data.awaiting_verification} /><Metric label="Verified / closed" value={workOrderSummary.data.verified} /></div>}
          </section>}
        </>}
  </div>
}

function WorkOrderQueue({ role, query }: { role: AuthUser['role']; query: UseQueryResult<Paginated<WorkOrderRecord>, Error> }) {
  const reviewer = role === 'ADMIN'
  const heading = reviewer ? 'Awaiting work verification' : 'My assigned work orders'
  if (query.isPending) return <section className="queue-section" aria-labelledby="dashboard-work-orders-title"><div className="queue-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h2 id="dashboard-work-orders-title">{heading}</h2></div><Link className="text-link" to="/work-orders">Open work orders <span aria-hidden="true">→</span></Link></div><div className="state-panel"><Loading label="Loading work orders" /></div></section>
  return <section className="queue-section" aria-labelledby="dashboard-work-orders-title"><div className="queue-heading"><div><p className="eyebrow">FIELD OPERATIONS</p><h2 id="dashboard-work-orders-title">{heading}</h2><p>{reviewer ? 'Completed tasks awaiting administrator verification.' : 'Tasks assigned to your technical staff account.'}</p></div><Link className="text-link" to="/work-orders">Open work orders <span aria-hidden="true">→</span></Link></div>
    {query.isError ? <ErrorState title="Work orders could not be loaded" detail="Your issue dashboard is still available. Try loading the work-order list again." onRetry={() => { void query.refetch() }} />
      : query.data.count === 0 ? <div className="queue-empty"><EmptyState title={reviewer ? 'No work orders awaiting review' : 'No work orders assigned'} detail={reviewer ? 'Completed technician work will appear here when it is ready for administrator verification.' : 'Work orders assigned to your account will appear here.'} /></div>
        : <div className="table-scroll"><table className="issue-table workspace-table"><thead><tr><th scope="col">Work order</th><th scope="col">Issue</th><th scope="col">Team</th><th scope="col">Status</th></tr></thead><tbody>{query.data.results.slice(0, 5).map((workOrder) => <tr key={workOrder.id}><td><Link className="ticket-link" to={`/work-orders/${workOrder.id}`}>{workOrder.number}</Link><small className="table-subtitle">{workOrder.title}</small></td><td><Link className="issue-title-link" to={`/issues/${workOrder.issue}`}>{workOrder.issue_ticket_number} · {workOrder.issue_title}</Link></td><td>{workOrder.team_name}</td><td><Badge tone={workOrder.status === 'CLOSED' || workOrder.status === 'VERIFIED' ? 'green' : workOrder.status === 'REWORK' ? 'red' : 'blue'}>{workOrder.status.replace(/_/g, ' ')}</Badge></td></tr>)}</tbody></table></div>}
  </section>
}

function Metric({ label, value, detail = '', tone = 'default', icon: Icon = BadgeCheck }: { label: string; value: number; detail?: string; tone?: 'default' | 'positive' | 'warning' | 'danger'; icon?: LucideIcon }) {
  return <article className={`workspace-metric workspace-metric--${tone}`}><div className="workspace-metric-heading"><span>{label}</span><Icon size={16} aria-hidden="true" /></div><strong>{value.toLocaleString()}</strong><small>{detail}</small></article>
}

function NetworkQualityMetric({ query }: { query: UseQueryResult<NetworkAnalyticsSummary, Error> }) {
  if (query.isPending) return <article className="workspace-metric workspace-metric--network" aria-busy="true"><div className="workspace-metric-heading"><span>Active Network Quality</span><Signal size={16} aria-hidden="true" /></div><strong>Loading</strong><small>Reading measured campus data…</small></article>
  if (query.isError) return <article className="workspace-metric workspace-metric--network"><div className="workspace-metric-heading"><span>Active Network Quality</span><Signal size={16} aria-hidden="true" /></div><strong>Unavailable</strong><button className="metric-retry" type="button" onClick={() => { void query.refetch() }}>Retry network summary</button></article>
  return <article className="workspace-metric workspace-metric--network"><div className="workspace-metric-heading"><span>Active Network Quality</span><Signal size={16} aria-hidden="true" /></div><strong>{query.data.overall_quality.replace(/_/g, ' ')}</strong><small>{query.data.total_measurements.toLocaleString()} measurements in the current window</small><Link className="metric-inline-link" to="/network-quality">View network analysis <ArrowRight size={13} aria-hidden="true" /></Link></article>
}
