import { useDeferredValue, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiRequest } from '../../lib/api'
import type { AssetOption, AuthUser, IssueCategory, IssuePriority, IssueRecord, IssueStatus, LocationOption, Paginated } from '../../types/api'
import { Badge, Button, EmptyState, ErrorState, Input, Loading, Select } from '../../components/ui'

const statuses: IssueStatus[] = ['OPEN', 'IN_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'REOPENED']
const priorities: IssuePriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const statusLabels: Record<IssueStatus, string> = {
  OPEN: 'Open', IN_REVIEW: 'In review', ASSIGNED: 'Assigned', IN_PROGRESS: 'In progress', RESOLVED: 'Resolved', CLOSED: 'Closed', REOPENED: 'Reopened',
}
const priorityLabels: Record<IssuePriority, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' }
const statusTones: Record<IssueStatus, 'neutral' | 'red' | 'blue' | 'green'> = {
  OPEN: 'blue', IN_REVIEW: 'neutral', ASSIGNED: 'neutral', IN_PROGRESS: 'blue', RESOLVED: 'green', CLOSED: 'neutral', REOPENED: 'red',
}
const priorityTones: Record<IssuePriority, 'neutral' | 'red' | 'blue' | 'green'> = { LOW: 'neutral', MEDIUM: 'blue', HIGH: 'red', CRITICAL: 'red' }
const PAGE_SIZE = 20

function friendlyError(error: unknown) {
  return error instanceof ApiError ? error.message : 'The service could not be reached. Try again shortly.'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function issueQuery(path: string) {
  return apiRequest<Paginated<IssueRecord>>(path)
}

export function IssueListPage({ user }: { user: AuthUser }) {
  const [params, setParams] = useSearchParams()
  const filterKey = params.toString()
  const queryString = useMemo(() => filterKey ? `?${filterKey}` : '', [filterKey])
  const issuesQuery = useQuery({ queryKey: ['issues', filterKey], queryFn: () => issueQuery(`/issues/${queryString}`) })
  const categoriesQuery = useQuery({ queryKey: ['issue-categories'], queryFn: () => apiRequest<Paginated<IssueCategory>>('/issue-categories/') })
  const operational = canSeeOperations(user.role)
  const teamsQuery = useQuery({ queryKey: ['teams'], queryFn: () => apiRequest<Paginated<{ id: number; name: string }>>('/teams/'), enabled: operational })
  const categories = categoriesQuery.data?.results ?? []
  const page = Number(params.get('page') ?? '1')
  const pages = Math.max(1, Math.ceil((issuesQuery.data?.count ?? 0) / PAGE_SIZE))

  function updateFilter(name: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    if (name !== 'page') next.delete('page')
    setParams(next)
  }

  return <section className="content-section" aria-labelledby="issue-list-title">
    <div className="section-heading"><div><h2 id="issue-list-title">Issue register</h2><p>Reports visible to your account, ordered by most recent.</p></div></div>
    <div className="filter-bar" aria-label="Filter issues">
      <label>Status<Select aria-label="Filter by status" value={params.get('status') ?? ''} onChange={(event) => updateFilter('status', event.target.value)}><option value="">All statuses</option>{statuses.map((status) => <option value={status} key={status}>{statusLabels[status]}</option>)}</Select></label>
      <label>Priority<Select aria-label="Filter by priority" value={params.get('priority') ?? ''} onChange={(event) => updateFilter('priority', event.target.value)}><option value="">All priorities</option>{priorities.map((priority) => <option value={priority} key={priority}>{priorityLabels[priority]}</option>)}</Select></label>
      <label>Category<Select aria-label="Filter by category" value={params.get('category') ?? ''} onChange={(event) => updateFilter('category', event.target.value)}><option value="">All categories</option>{categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}</Select></label>
      {operational && <label>Team<Select aria-label="Filter by team" value={params.get('assigned_team') ?? ''} onChange={(event) => updateFilter('assigned_team', event.target.value)}><option value="">All teams</option>{(teamsQuery.data?.results ?? []).map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}</Select></label>}
      {operational && <label>SLA state<Select aria-label="Filter by SLA state" value={params.get('sla_state') ?? ''} onChange={(event) => updateFilter('sla_state', event.target.value)}><option value="">Any SLA state</option><option value="AT_RISK">At risk</option><option value="BREACHED">Breached</option><option value="COMPLETED">Completed</option><option value="NOT_CONFIGURED">Not configured</option></Select></label>}
      {operational && <label className="checkbox-filter"><input type="checkbox" checked={params.get('unassigned') === 'true'} onChange={(event) => updateFilter('unassigned', event.target.checked ? 'true' : '')} /> Unassigned only</label>}
      <label>From date<Input aria-label="Filter from date" type="date" value={params.get('created_after') ?? ''} onChange={(event) => updateFilter('created_after', event.target.value)} /></label>
      <label>To date<Input aria-label="Filter to date" type="date" value={params.get('created_before') ?? ''} onChange={(event) => updateFilter('created_before', event.target.value)} /></label>
    </div>
    {categoriesQuery.isError && <ErrorState title="Categories could not be loaded" detail={friendlyError(categoriesQuery.error)} />}
    {issuesQuery.isPending ? <div className="state-panel"><Loading label="Loading issues" /></div>
      : issuesQuery.isError ? <ErrorState title="Issues could not be loaded" detail={friendlyError(issuesQuery.error)} />
        : issuesQuery.data.count === 0 ? <div className="state-panel"><EmptyState title="No issues found" detail="Change the filters or report a campus issue to start a record." /><Link className="button button--primary" to="/issues/new">Report an issue</Link></div>
          : <>
            <div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Ticket</th><th scope="col">Issue</th><th scope="col">Category</th><th scope="col">Location</th><th scope="col">Priority</th><th scope="col">Status</th>{operational && <><th scope="col">Team</th><th scope="col">SLA</th></>}<th scope="col">Reported by</th><th scope="col">Created</th></tr></thead>
              <tbody>{issuesQuery.data.results.map((issue) => <tr key={issue.id}>
                <td><Link className="ticket-link" to={`/issues/${issue.id}`}>{issue.ticket_number}</Link></td>
                <td><Link className="issue-title-link" to={`/issues/${issue.id}`}>{issue.title}</Link></td>
                <td>{issue.category.name}</td><td>{issue.location_name}</td>
                <td><Badge tone={priorityTones[issue.priority]}>{priorityLabels[issue.priority]}</Badge></td>
                <td><Badge tone={statusTones[issue.status]}>{statusLabels[issue.status]}</Badge></td>
                {operational && <><td>{issue.assigned_team_name ?? 'Unassigned'}</td><td>{issue.sla_state?.replace(/_/g, ' ') ?? '—'}</td></>}
                <td>{issue.reporter_name ?? (issue.reporter === user.id ? 'You' : '—')}</td>
                <td className="date-cell">{formatDate(issue.created_at)}</td>
              </tr>)}</tbody>
            </table></div>
            <div className="pagination-bar"><span>{issuesQuery.data.count} issue{issuesQuery.data.count === 1 ? '' : 's'} · page {page} of {pages}</span><div><Button disabled={!issuesQuery.data.previous} onClick={() => updateFilter('page', String(Math.max(1, page - 1)))}>Previous</Button><Button disabled={!issuesQuery.data.next} onClick={() => updateFilter('page', String(page + 1))}>Next</Button></div></div>
          </>}
  </section>
}

export function IssueCreatePage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [location, setLocation] = useState('')
  const [priority, setPriority] = useState<IssuePriority>('MEDIUM')
  const [asset, setAsset] = useState('')
  const [locationSearch, setLocationSearch] = useState('')
  const [assetSearch, setAssetSearch] = useState('')
  const [description, setDescription] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const deferredLocationSearch = useDeferredValue(locationSearch)
  const deferredAssetSearch = useDeferredValue(assetSearch)
  const categoriesQuery = useQuery({ queryKey: ['issue-categories'], queryFn: () => apiRequest<Paginated<IssueCategory>>('/issue-categories/') })
  const locationsQuery = useQuery({ queryKey: ['issue-form-locations', deferredLocationSearch], queryFn: () => apiRequest<Paginated<LocationOption>>(`/locations/${deferredLocationSearch ? `?search=${encodeURIComponent(deferredLocationSearch)}` : ''}`) })
  const assetsQuery = useQuery({ queryKey: ['issue-form-assets', deferredAssetSearch], queryFn: () => apiRequest<Paginated<AssetOption>>(`/assets/${deferredAssetSearch ? `?search=${encodeURIComponent(deferredAssetSearch)}` : ''}`) })
  const createIssue = useMutation({
    mutationFn: (formData: FormData) => apiRequest<IssueRecord>('/issues/', { method: 'POST', body: formData }),
    onSuccess: (issue) => navigate(`/issues/${issue.id}`, { replace: true }),
  })

  useEffect(() => {
    if (!photo) { setPhotoPreview(null); return }
    const preview = URL.createObjectURL(photo)
    setPhotoPreview(preview)
    return () => URL.revokeObjectURL(preview)
  }, [photo])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData()
    data.append('title', title.trim())
    data.append('category', category)
    data.append('location', location)
    data.append('priority', priority)
    data.append('description', description.trim())
    if (asset) data.append('asset', asset)
    if (photo) data.append('photo', photo)
    createIssue.mutate(data)
  }

  const optionsPending = categoriesQuery.isPending || locationsQuery.isPending || assetsQuery.isPending
  const optionsError = categoriesQuery.error ?? locationsQuery.error ?? assetsQuery.error
  return <section className="report-layout" aria-labelledby="report-title">
    <div className="report-intro"><div className="eyebrow">CAMPUS SERVICE REQUEST</div><h2 id="report-title">Tell us what needs attention</h2><p>Share the location and a short description. The operations team can follow up from your report.</p><div className="privacy-note"><span aria-hidden="true">i</span><p>Your report is linked to your account so you can track its status.</p></div></div>
    {optionsPending ? <div className="state-panel"><Loading label="Loading categories and campus locations" /></div>
      : optionsError ? <ErrorState title="The issue form could not load" detail={friendlyError(optionsError)} />
        : <form className="report-form" onSubmit={submit}>
          {createIssue.isError && <div className="form-error" role="alert">{friendlyError(createIssue.error)}</div>}
          <div className="form-field"><label htmlFor="issue-title">What is the problem? <span className="required-mark">Required</span></label><Input id="issue-title" name="title" value={title} onChange={(event) => setTitle(event.target.value)} minLength={4} maxLength={160} autoFocus required placeholder="For example, projector is not turning on" /><small>Short summary, up to 160 characters.</small></div>
          <div className="form-row">
            <div className="form-field"><label htmlFor="issue-category">Category <span className="required-mark">Required</span></label><Select id="issue-category" value={category} onChange={(event) => setCategory(event.target.value)} required><option value="">Choose a category</option>{categoriesQuery.data?.results.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></div>
            <div className="form-field"><label htmlFor="issue-location-search">Location <span className="required-mark">Required</span></label><Input id="issue-location-search" type="search" value={locationSearch} onChange={(event) => setLocationSearch(event.target.value)} placeholder="Search campus locations" /><Select id="issue-location" value={location} onChange={(event) => setLocation(event.target.value)} required><option value="">Choose a location</option>{locationsQuery.data?.results.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</Select><small>{locationsQuery.data?.count ?? 0} matching locations</small></div>
          </div>
          <div className="form-row">
            <div className="form-field"><label htmlFor="issue-priority">Priority</label><Select id="issue-priority" value={priority} onChange={(event) => setPriority(event.target.value as IssuePriority)}>{priorities.map((item) => <option key={item} value={item}>{priorityLabels[item]}</option>)}</Select><small>Choose critical only if there is immediate risk to safety or essential service.</small></div>
            <div className="form-field"><label htmlFor="issue-asset-search">Related asset <span className="optional-mark">Optional</span></label><Input id="issue-asset-search" type="search" value={assetSearch} onChange={(event) => setAssetSearch(event.target.value)} placeholder="Search by name or asset code" /><Select id="issue-asset" value={asset} onChange={(event) => { const next = event.target.value; setAsset(next); const selected = assetsQuery.data?.results.find((item) => String(item.id) === next); if (selected) { setLocation(String(selected.location)); setLocationSearch(selected.location_name) } }}><option value="">No asset selected</option>{assetsQuery.data?.results.map((item) => <option key={item.id} value={item.id}>{item.asset_code} · {item.name}</option>)}</Select><small>{assetsQuery.data?.count ?? 0} matching assets · selecting an asset sets its registered location.</small></div>
          </div>
          <div className="form-field"><label htmlFor="issue-description">Description <span className="required-mark">Required</span></label><textarea id="issue-description" className="field text-area" name="description" value={description} onChange={(event) => setDescription(event.target.value)} minLength={10} maxLength={5000} rows={4} required placeholder="Add details that will help someone locate and understand the problem." /><small>Include useful details such as when it started or what you observed.</small></div>
          <div className="form-field"><label htmlFor="issue-photo">Photo <span className="optional-mark">Optional</span></label><input id="issue-photo" className="file-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} /><small>JPEG, PNG, or WebP · maximum 5 MB.</small>{photoPreview && <div className="photo-preview"><img src={photoPreview} alt="Selected issue photo preview" /><Button type="button" onClick={() => setPhoto(null)}>Remove photo</Button></div>}</div>
          <div className="form-actions"><Button type="button" onClick={() => navigate('/issues')}>Cancel</Button><Button variant="primary" type="submit" disabled={createIssue.isPending}>{createIssue.isPending ? 'Submitting…' : 'Submit issue'}</Button></div>
        </form>}
  </section>
}

const transitions: Partial<Record<IssueStatus, IssueStatus[]>> = {
  OPEN: ['IN_REVIEW'], IN_REVIEW: ['ASSIGNED'], ASSIGNED: ['IN_PROGRESS'], IN_PROGRESS: ['RESOLVED'], RESOLVED: ['CLOSED', 'REOPENED'], CLOSED: ['REOPENED'], REOPENED: ['IN_REVIEW'],
}
const managers = new Set<AuthUser['role']>(['FACILITY_MANAGER', 'IT_MANAGER', 'DEPARTMENT_HEAD', 'CAMPUS_ADMIN', 'SYSTEM_ADMIN'])

export function IssueDetailPage({ user }: { user: AuthUser }) {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
  const issueQuery = useQuery({ queryKey: ['issue', id], queryFn: () => apiRequest<IssueRecord>(`/issues/${id}/`) })
  const statusUpdate = useMutation({
    mutationFn: (nextStatus: IssueStatus) => apiRequest<IssueRecord>(`/issues/${id}/status/`, { method: 'POST', body: JSON.stringify({ status: nextStatus }) }),
    onSuccess: (issue) => {
      queryClient.setQueryData(['issue', id], issue)
      queryClient.invalidateQueries({ queryKey: ['issues'] })
    },
  })

  if (issueQuery.isPending) return <div className="state-panel"><Loading label="Loading issue" /></div>
  if (issueQuery.isError) return <ErrorState title="Issue could not be loaded" detail={friendlyError(issueQuery.error)} />
  const issue = issueQuery.data
  const canUpdate = managers.has(user.role)
    || (user.role === 'TECHNICIAN' && issue.assigned_to === user.id)
    || (user.role === 'SUPERVISOR' && issue.assigned_team !== null && user.team_ids.includes(issue.assigned_team))
  const nextStatuses = canUpdate ? transitions[issue.status] ?? [] : []

  return <section className="issue-detail-layout">
    <div className="detail-main">
      <div className="detail-title-row"><div><p className="ticket-kicker">{issue.ticket_number}</p><h2>{issue.title}</h2></div><Badge tone={statusTones[issue.status]}>{statusLabels[issue.status]}</Badge></div>
      {statusUpdate.isError && <div className="form-error" role="alert">{friendlyError(statusUpdate.error)}</div>}
      {nextStatuses.length > 0 && <div className="status-action"><label htmlFor="next-status">Update status</label><Select id="next-status" value="" disabled={statusUpdate.isPending} onChange={(event) => { if (event.target.value) statusUpdate.mutate(event.target.value as IssueStatus) }}><option value="">Choose next status</option>{nextStatuses.map((next) => <option key={next} value={next}>{statusLabels[next]}</option>)}</Select></div>}
      <section className="detail-section"><h3>Description</h3><p className="issue-description">{issue.description}</p></section>
      <section className="detail-section"><h3>Photos</h3>{issue.attachments?.length ? <div className="attachment-grid">{issue.attachments.map((attachment) => <figure key={attachment.id}><a href={attachment.file_url} target="_blank" rel="noreferrer"><img src={attachment.file_url} alt={`Attachment uploaded by ${attachment.uploaded_by_name}`} /></a><figcaption>{attachment.uploaded_by_name} · {formatDate(attachment.created_at)}</figcaption></figure>)}</div> : <p className="muted-copy">No photos were attached.</p>}</section>
      <section className="detail-section"><h3>Record history</h3>{issue.events?.length ? <ol className="timeline">{issue.events.map((event) => <li key={event.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{event.from_status ? `${statusLabels[event.from_status]} → ${statusLabels[event.to_status]}` : `Issue ${statusLabels[event.to_status].toLowerCase()}`}</strong><p>{event.note || 'Status updated'}{event.actor_name ? ` · ${event.actor_name}` : ''}</p><time dateTime={event.created_at}>{formatDate(event.created_at)}</time></div></li>)}</ol> : <p className="muted-copy">No history events are recorded.</p>}</section>
    </div>
    <aside className="detail-aside" aria-label="Issue information"><h3>Issue information</h3><Info label="Category" value={issue.category.name} /><Info label="Location" value={issue.location_name} /><Info label="Priority" value={priorityLabels[issue.priority]} /><Info label="Related asset" value={issue.asset_name ?? 'None'} /><Info label="Reported by" value={issue.reporter_name ?? (issue.reporter === user.id ? 'You' : 'Not available')} />{canSeeOperations(user.role) && <><Info label="Assigned team" value={issue.assigned_team_name ?? 'Not assigned'} /><Info label="Assigned to" value={issue.assigned_to_name ?? 'Not assigned'} /><SlaPanel issue={issue} />{issue.assignment_history?.length ? <section className="assignment-history"><h4>Assignment history</h4>{issue.assignment_history.map((item, index) => <p key={`${item.created_at}-${index}`}><strong>{item.team ?? 'Unassigned'}</strong> · {item.reason}{item.rule ? ` · Rule: ${item.rule}` : ''}</p>)}</section> : null}{(user.role === 'SUPERVISOR' || managers.has(user.role)) && <AssignmentForm issue={issue} />}</>}<Info label="Created" value={formatDate(issue.created_at)} /><Info label="Updated" value={formatDate(issue.updated_at)} />{issue.resolved_at && <Info label="Resolved" value={formatDate(issue.resolved_at)} />}{issue.closed_at && <Info label="Closed" value={formatDate(issue.closed_at)} />}</aside>
  </section>
}

function Info({ label, value }: { label: string; value: string }) {
  return <div className="info-row"><span>{label}</span><strong>{value}</strong></div>
}

function canSeeOperations(role: AuthUser['role']) {
  return role === 'TECHNICIAN' || role === 'SUPERVISOR' || managers.has(role)
}

function SlaPanel({ issue }: { issue: IssueRecord }) {
  const text: Record<string, string> = { ON_TRACK: 'On track', AT_RISK: 'At risk', BREACHED: 'Breached', COMPLETED: 'Completed', NOT_CONFIGURED: 'No matching policy' }
  return <section className="sla-panel"><h4>Service targets</h4><p><strong>Policy</strong><span>{issue.sla_policy_name ?? 'Not configured'}</span></p><p><strong>Response SLA</strong><span>{issue.response_due_at ? formatDate(issue.response_due_at) : '—'} · {text[issue.response_sla_state ?? 'NOT_CONFIGURED']}</span></p><p><strong>Resolution SLA</strong><span>{issue.resolution_due_at ? formatDate(issue.resolution_due_at) : '—'} · {text[issue.resolution_sla_state ?? 'NOT_CONFIGURED']}</span></p>{issue.current_escalation_level ? <p><strong>Escalation</strong><span>Level {issue.current_escalation_level}</span></p> : null}</section>
}

function AssignmentForm({ issue }: { issue: IssueRecord }) {
  const cache = useQueryClient()
  const teams = useQuery({ queryKey: ['teams'], queryFn: () => apiRequest<Paginated<{ id: number; name: string; is_active: boolean }>>('/teams/') })
  const mutation = useMutation({ mutationFn: (body: { team: number; reason: string }) => apiRequest(`/issues/${issue.id}/assign/`, { method: 'POST', body: JSON.stringify(body) }), onSuccess: () => { void cache.invalidateQueries({ queryKey: ['issue', String(issue.id)] }); void cache.invalidateQueries({ queryKey: ['issues'] }) } })
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); mutation.mutate({ team: Number(data.get('team')), reason: String(data.get('reason')) }) }
  if (teams.isPending || teams.isError) return null
  return <form className="assignment-form" onSubmit={submit}><h4>Reassign team</h4><label>Team<Select name="team" defaultValue={issue.assigned_team ?? ''} required><option value="">Select team</option>{(teams.data.results ?? []).filter((team) => team.is_active).map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</Select></label><label>Reason<Input name="reason" minLength={3} maxLength={500} required /></label>{mutation.isError && <p className="form-error" role="alert">{friendlyError(mutation.error)}</p>}{mutation.isSuccess && <p role="status">Assignment updated.</p>}<Button variant="primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Assigning…' : 'Assign team'}</Button></form>
}
