import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '../../lib/api'
import type { IssueRecord, Paginated } from '../../types/api'
import { Badge, EmptyState, ErrorState, Loading } from '../../components/ui'

export default function DashboardPage() {
  const dashboard = useQuery({
    queryKey: ['dashboard-issues'],
    queryFn: async () => {
      const [all, open, resolved] = await Promise.all([
        apiRequest<Paginated<IssueRecord>>('/issues/'),
        apiRequest<Paginated<IssueRecord>>('/issues/?status=OPEN'),
        apiRequest<Paginated<IssueRecord>>('/issues/?status=RESOLVED'),
      ])
      return { all, open, resolved }
    },
  })

  return <>
    {dashboard.isPending ? <div className="state-panel"><Loading label="Loading your issue summary" /></div>
      : dashboard.isError ? <ErrorState title="The issue summary could not be loaded" detail="Check your connection and try again." />
        : <section className="metric-grid metric-grid--phase-two" aria-label="Issue summary">
          <Metric label="Issues in your scope" value={dashboard.data.all.count} />
          <Metric label="Open issues" value={dashboard.data.open.count} />
          <Metric label="Resolved issues" value={dashboard.data.resolved.count} />
        </section>}
    <section className="dashboard-grid dashboard-grid--phase-two">
      <section className="panel panel--wide"><div className="panel-heading"><div><h2>Recent issues</h2><p>Latest reports visible to your account</p></div><Link className="text-link" to="/issues">View all</Link></div>
        {dashboard.isPending ? <Loading label="Loading recent issues" />
          : dashboard.isError ? <ErrorState title="Recent issues are unavailable" detail="Try again in a moment." />
            : dashboard.data.all.results.length === 0 ? <EmptyState title="No issues reported yet" detail="When a campus issue is reported, it will appear here." />
              : <ul className="recent-issues">{dashboard.data.all.results.slice(0, 6).map((issue) => <li key={issue.id}><Link to={`/issues/${issue.id}`}><span><strong>{issue.title}</strong><small>{issue.ticket_number} · {issue.category.name} · {issue.location_name}</small></span><Badge tone={issue.status === 'RESOLVED' || issue.status === 'CLOSED' ? 'green' : 'blue'}>{issue.status.replace(/_/g, ' ')}</Badge></Link></li>)}</ul>}
      </section>
      <section className="panel report-shortcut"><div className="eyebrow">CAMPUS SUPPORT</div><h2>Something needs attention?</h2><p>Send a clear report with a location and category. You can follow its status here.</p><Link className="button button--primary" to="/issues/new">Report an issue</Link></section>
    </section>
  </>
}

function Metric({ label, value }: { label: string; value: number }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span></div><div className="metric-value">{value.toLocaleString()}</div><div className="metric-note">From current issue records</div></article>
}
