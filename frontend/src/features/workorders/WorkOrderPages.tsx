import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiRequest } from '../../lib/api'
import type { AuthUser, Paginated, WorkOrderDetail, WorkOrderRecord, WorkOrderStatus } from '../../types/api'
import { Badge, Button, EmptyState, ErrorState, Input, Loading, Select } from '../../components/ui'

type TeamOption = { id: number; name: string; is_active: boolean; members: number[] }
type TechnicianOption = { id: number; full_name: string; email: string }
export type WorkOrderSummary = { open: number; in_progress: number; awaiting_verification: number; verified: number }

const managerRoles = new Set<AuthUser['role']>(['SUPERVISOR', 'FACILITY_MANAGER', 'IT_MANAGER', 'DEPARTMENT_HEAD', 'CAMPUS_ADMIN', 'SYSTEM_ADMIN'])
const statusLabels: Record<WorkOrderStatus, string> = {
  ASSIGNED: 'Assigned', ACCEPTED: 'Accepted', IN_PROGRESS: 'In progress', COMPLETED: 'Awaiting verification',
  VERIFIED: 'Verified', REWORK: 'Rework required', CANCELLED: 'Cancelled', CLOSED: 'Closed',
}
const statusTone: Record<WorkOrderStatus, 'neutral' | 'red' | 'blue' | 'green'> = {
  ASSIGNED: 'blue', ACCEPTED: 'blue', IN_PROGRESS: 'blue', COMPLETED: 'neutral', VERIFIED: 'green', REWORK: 'red', CANCELLED: 'neutral', CLOSED: 'green',
}

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'The request could not be completed. Check the connection and try again.'
}
function date(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
}
function refreshWorkOrders(cache: ReturnType<typeof useQueryClient>, id?: number) {
  void cache.invalidateQueries({ queryKey: ['work-orders'] })
  void cache.invalidateQueries({ queryKey: ['work-order-summary'] })
  if (id) void cache.invalidateQueries({ queryKey: ['work-order', String(id)] })
  void cache.invalidateQueries({ queryKey: ['issues'] })
  void cache.invalidateQueries({ queryKey: ['dashboard-issues'] })
}

export function WorkOrderListPage({ user }: { user: AuthUser }) {
  const [filter, setFilter] = useState('')
  const query = useQuery({ queryKey: ['work-orders', filter], queryFn: () => apiRequest<Paginated<WorkOrderRecord>>(`/work-orders/${filter ? `?status=${filter}` : ''}`) })
  const summary = useQuery({ queryKey: ['work-order-summary'], queryFn: () => apiRequest<WorkOrderSummary>('/work-orders/summary/') })
  return <section className="work-order-page" aria-labelledby="work-orders-title">
    <div className="section-heading"><div><h2 id="work-orders-title">{user.role === 'TECHNICIAN' ? 'My work orders' : user.role === 'SUPERVISOR' ? 'Team work orders' : 'Operational work orders'}</h2><p>Field tasks linked to existing campus service issues.</p></div>
      <label className="work-order-filter">Status<Select aria-label="Filter work orders by status" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">All statuses</option>{Object.entries(statusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</Select></label>
    </div>
    {summary.data && <div className="work-order-metrics" aria-label="Work order summary"><Metric label="Open" value={summary.data.open} /><Metric label="In progress" value={summary.data.in_progress} /><Metric label="Awaiting verification" value={summary.data.awaiting_verification} /><Metric label="Verified / closed" value={summary.data.verified} /></div>}
    {summary.isError && <ErrorState title="Work-order summary unavailable" detail={errorMessage(summary.error)} onRetry={() => { void summary.refetch() }} />}
    {query.isPending ? <div className="state-panel"><Loading label="Loading work orders" /></div>
      : query.isError ? <ErrorState title="Work orders could not be loaded" detail={errorMessage(query.error)} onRetry={() => { void query.refetch() }} />
        : query.data.count === 0 ? <div className="state-panel"><EmptyState title="No work orders in this view" detail="Work orders appear here when operational staff create or assign field tasks." /></div>
          : <div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Work order</th><th scope="col">Issue</th><th scope="col">Team</th><th scope="col">Technician</th><th scope="col">Priority</th><th scope="col">Status</th><th scope="col">Created</th></tr></thead><tbody>{query.data.results.map((workOrder) => <tr key={workOrder.id}>
            <td><Link className="ticket-link" to={`/work-orders/${workOrder.id}`}>{workOrder.number}</Link></td><td><span>{workOrder.title}</span><small className="table-subtitle">{workOrder.issue_ticket_number} · {workOrder.issue_title}</small></td><td>{workOrder.team_name}</td><td>{workOrder.assigned_to_name ?? 'Unassigned'}</td><td><Badge tone={workOrder.priority === 'CRITICAL' || workOrder.priority === 'HIGH' ? 'red' : 'blue'}>{workOrder.priority}</Badge></td><td><Badge tone={statusTone[workOrder.status]}>{statusLabels[workOrder.status]}</Badge></td><td className="date-cell">{date(workOrder.created_at)}</td>
          </tr>)}</tbody></table><p className="work-order-count">{query.data.count} work order{query.data.count === 1 ? '' : 's'}</p></div>}
  </section>
}

export function WorkOrderDetailPage({ user }: { user: AuthUser }) {
  const { id = '' } = useParams()
  const workOrderId = Number(id)
  const cache = useQueryClient()
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['work-order', id], queryFn: () => apiRequest<WorkOrderDetail>(`/work-orders/${id}/`) })
  const manager = managerRoles.has(user.role)
  const technician = user.role === 'TECHNICIAN'
  const [note, setNote] = useState('')
  const [materialName, setMaterialName] = useState('')
  const [materialQuantity, setMaterialQuantity] = useState('1')
  const [materialNote, setMaterialNote] = useState('')
  const [resolution, setResolution] = useState('')
  const [assignmentReason, setAssignmentReason] = useState('')
  const [reviewReason, setReviewReason] = useState('')
  const [cancelReason, setCancelReason] = useState('')
  const [teamId, setTeamId] = useState('')
  const [technicianId, setTechnicianId] = useState('')
  const [evidence, setEvidence] = useState<File | null>(null)
  const [caption, setCaption] = useState('')
  const evidenceInput = useRef<HTMLInputElement>(null)
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: BodyInit }) => apiRequest<WorkOrderDetail>(`/work-orders/${id}/${path}/`, { method: 'POST', body: body ?? JSON.stringify({}) }),
    onSuccess: (result, variables) => {
      cache.setQueryData(['work-order', id], result)
      refreshWorkOrders(cache, workOrderId)
      if (variables.path === 'notes') setNote('')
      if (variables.path === 'materials') { setMaterialName(''); setMaterialNote('') }
      if (variables.path === 'evidence') { setEvidence(null); setCaption(''); if (evidenceInput.current) evidenceInput.current.value = '' }
    },
  })
  const teams = useQuery({ queryKey: ['teams'], queryFn: () => apiRequest<Paginated<TeamOption>>('/teams/'), enabled: manager })
  const eligibleTeams = (teams.data?.results ?? []).filter((team) => team.is_active && (user.role !== 'SUPERVISOR' || user.team_ids.includes(team.id)))
  const technicians = useQuery({ queryKey: ['work-order-technicians', teamId], queryFn: () => apiRequest<TechnicianOption[]>(`/work-order-technicians/?team=${teamId}`), enabled: manager && Boolean(teamId) })
  const selectedTechnicianId = technicianId || (teamId === String(query.data?.team ?? '') ? String(query.data?.assigned_to ?? '') : '')

  useEffect(() => { if (query.data && !teamId) setTeamId(String(query.data.team)) }, [query.data, teamId])

  function send(path: string, body?: object) {
    mutation.mutate({ path, body: body ? JSON.stringify(body) : undefined })
  }
  function submitNote(event: FormEvent<HTMLFormElement>) { event.preventDefault(); send('notes', { body: note }) }
  function submitMaterial(event: FormEvent<HTMLFormElement>) { event.preventDefault(); send('materials', { name: materialName, quantity: materialQuantity, note: materialNote }) }
  function submitResolution(event: FormEvent<HTMLFormElement>) { event.preventDefault(); send('complete', { resolution_summary: resolution }) }
  function submitRework(event: FormEvent<HTMLFormElement>) { event.preventDefault(); send('rework', { reason: reviewReason }) }
  function submitAssign(event: FormEvent<HTMLFormElement>) { event.preventDefault(); send('assign', { team: Number(teamId), technician: selectedTechnicianId ? Number(selectedTechnicianId) : null, reason: assignmentReason }) }
  function submitEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!evidence) return
    const data = new FormData(); data.set('file', evidence); data.set('caption', caption)
    mutation.mutate({ path: 'evidence', body: data })
  }

  if (query.isPending) return <div className="state-panel"><Loading label="Loading work order" /></div>
  if (query.isError) return <ErrorState title="Work order could not be loaded" detail={errorMessage(query.error)} onRetry={() => { void query.refetch() }} />
  const workOrder = query.data
  const activeTech = technician && workOrder.assigned_to === user.id
  const activeFieldState = ['ACCEPTED', 'IN_PROGRESS', 'REWORK'].includes(workOrder.status)
  return <section className="work-order-detail" aria-labelledby="work-order-title">
    <div className="work-order-title-row"><div><p className="ticket-kicker">Work order {workOrder.number} · originating issue <Link to={`/issues/${workOrder.issue}`}>{workOrder.issue_ticket_number}</Link></p><h2 id="work-order-title">{workOrder.title}</h2><p>{workOrder.issue_title}</p></div><Badge tone={statusTone[workOrder.status]}>{statusLabels[workOrder.status]}</Badge></div>
    {!['CANCELLED'].includes(workOrder.status) && <WorkOrderLifecycle status={workOrder.status} />}
    {mutation.isError && <div className="form-error" role="alert">{errorMessage(mutation.error)}</div>}
    {mutation.isSuccess && <p className="work-order-success" role="status">Work-order update saved.</p>}
    <div className="work-order-detail-grid"><div className="work-order-main">
      <section className="detail-section"><h3>Field instructions</h3><p>{workOrder.instructions || 'No additional instructions were provided.'}</p></section>
      {workOrder.rework_reason && <div className="work-order-callout" role="status"><strong>Additional work requested</strong><p>{workOrder.rework_reason}</p></div>}
      {activeTech && <section className="work-order-actions" aria-label="Technician actions">
        {workOrder.status === 'ASSIGNED' && <Button variant="primary" disabled={mutation.isPending} onClick={() => send('accept')}>Accept work order</Button>}
        {(workOrder.status === 'ACCEPTED' || workOrder.status === 'REWORK') && <Button variant="primary" disabled={mutation.isPending} onClick={() => send('start')}>Start field work</Button>}
        {activeFieldState && <>
          <form className="work-order-form" onSubmit={submitNote}><h3>Technician notes</h3><label htmlFor="wo-note">Progress note</label><textarea id="wo-note" className="field" value={note} onChange={(event) => setNote(event.target.value)} minLength={2} maxLength={5000} required rows={3} /><Button disabled={mutation.isPending}>Add note</Button></form>
          <form className="work-order-form" onSubmit={submitEvidence}><h3>Evidence photos</h3><label htmlFor="wo-evidence">Upload image</label><input ref={evidenceInput} id="wo-evidence" className="file-input" type="file" accept="image/jpeg,image/png,image/webp" required onChange={(event) => setEvidence(event.target.files?.[0] ?? null)} /><label htmlFor="wo-caption">Caption <span className="optional-mark">Optional</span></label><Input id="wo-caption" value={caption} maxLength={240} onChange={(event) => setCaption(event.target.value)} /><small>Private JPEG, PNG, or WebP image · maximum 5 MB.</small><Button disabled={mutation.isPending || !evidence}>{mutation.isPending ? 'Uploading…' : 'Upload evidence'}</Button></form>
        </>}
        {workOrder.status === 'IN_PROGRESS' && <>
          <form className="work-order-form" onSubmit={submitMaterial}><h3>Materials used</h3><label htmlFor="material-name">Material name</label><Input id="material-name" value={materialName} maxLength={160} required onChange={(event) => setMaterialName(event.target.value)} /><label htmlFor="material-quantity">Quantity</label><Input id="material-quantity" type="number" min="0.01" step="0.01" value={materialQuantity} required onChange={(event) => setMaterialQuantity(event.target.value)} /><label htmlFor="material-note">Note <span className="optional-mark">Optional</span></label><Input id="material-note" value={materialNote} maxLength={500} onChange={(event) => setMaterialNote(event.target.value)} /><Button disabled={mutation.isPending}>Record material</Button></form>
          <form className="work-order-form" onSubmit={submitResolution}><h3>Submit resolution</h3><label htmlFor="wo-resolution">Work performed, finding, action taken, and current condition</label><textarea id="wo-resolution" className="field" value={resolution} onChange={(event) => setResolution(event.target.value)} minLength={20} maxLength={5000} required rows={5} /><small>At least 20 characters. A supervisor must verify before the issue can be resolved.</small><Button variant="primary" disabled={mutation.isPending}>Complete work order</Button></form>
        </>}
      </section>}
      <section className="detail-section"><h3>Resolution summary</h3>{workOrder.resolution_summary ? <p className="issue-description">{workOrder.resolution_summary}</p> : <p className="muted-copy">The technician has not submitted a resolution yet.</p>}</section>
      <section className="detail-section"><h3>Evidence</h3>{workOrder.evidence.length ? <div className="attachment-grid">{workOrder.evidence.map((item) => <figure key={item.id}><a href={item.file_url} target="_blank" rel="noreferrer"><img src={item.file_url} alt={item.caption || `Evidence uploaded by ${item.uploaded_by_name}`} /></a><figcaption>{item.caption || 'Work evidence'} · {item.uploaded_by_name} · {date(item.created_at)}</figcaption></figure>)}</div> : <p className="muted-copy">No work-order evidence has been uploaded.</p>}</section>
      <section className="detail-section"><h3>Technician notes</h3>{workOrder.notes.length ? <ol className="timeline">{workOrder.notes.map((entry) => <li key={entry.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{entry.author_name}</strong><p>{entry.body}</p><time dateTime={entry.created_at}>{date(entry.created_at)}</time></div></li>)}</ol> : <p className="muted-copy">No technician notes yet.</p>}</section>
      <section className="detail-section"><h3>Materials recorded</h3>{workOrder.materials.length ? <ul className="work-order-materials">{workOrder.materials.map((item) => <li key={item.id}><strong>{item.name}</strong> · {item.quantity}{item.note && <span> · {item.note}</span>}</li>)}</ul> : <p className="muted-copy">No materials recorded.</p>}</section>
      <section className="detail-section"><h3>Work-order history</h3>{workOrder.events.length ? <ol className="timeline">{workOrder.events.map((event) => <li key={event.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{event.event_type.replace(/_/g, ' ')}</strong><p>{event.note}{event.actor_name ? ` · ${event.actor_name}` : ''}</p><time dateTime={event.created_at}>{date(event.created_at)}</time></div></li>)}</ol> : <p className="muted-copy">No history recorded.</p>}</section>
    </div><aside className="detail-aside work-order-aside" aria-label="Work order details"><h3>Operational details</h3><Info label="Status" value={statusLabels[workOrder.status]} /><Info label="Team" value={workOrder.team_name} /><Info label="Technician" value={workOrder.assigned_to_name ?? 'Not assigned'} /><Info label="Priority" value={workOrder.priority} /><Info label="Issue SLA deadline" value={date(workOrder.issue_sla_deadline)} /><Info label="Created" value={date(workOrder.created_at)} /><Info label="Accepted" value={date(workOrder.accepted_at)} /><Info label="Started" value={date(workOrder.started_at)} /><Info label="Completed" value={date(workOrder.completed_at)} /><Info label="Verified" value={date(workOrder.verified_at)} />
      {manager && workOrder.status !== 'COMPLETED' && workOrder.status !== 'VERIFIED' && workOrder.status !== 'CLOSED' && workOrder.status !== 'CANCELLED' && <form className="assignment-form" onSubmit={submitAssign}><h4>Assign technician</h4><label htmlFor="wo-team">Team</label><Select id="wo-team" value={teamId || String(workOrder.team)} onChange={(event) => { setTeamId(event.target.value); setTechnicianId('') }}><option value="">Select a team</option>{eligibleTeams.map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}</Select><label htmlFor="wo-tech">Active technician</label><Select id="wo-tech" value={selectedTechnicianId} onChange={(event) => setTechnicianId(event.target.value)} disabled={!technicians.data?.length}><option value="">Select a technician</option>{(technicians.data ?? []).map((member) => <option value={member.id} key={member.id}>{member.full_name} · {member.email}</option>)}</Select>{technicians.isError && <p className="form-error" role="alert">{errorMessage(technicians.error)}</p>}<label htmlFor="wo-assign-reason">Reason</label><Input id="wo-assign-reason" value={assignmentReason} minLength={3} maxLength={500} required onChange={(event) => setAssignmentReason(event.target.value)} /><Button variant="primary" disabled={mutation.isPending || !selectedTechnicianId}>{workOrder.assigned_to ? 'Reassign work' : 'Assign work'}</Button></form>}
      {manager && workOrder.status === 'COMPLETED' && <div className="work-order-review"><h4>Supervisor verification</h4><Button variant="primary" disabled={mutation.isPending} onClick={() => send('verify')}>Verify completion</Button><form onSubmit={submitRework}><label htmlFor="rework-reason">Return for additional work</label><textarea id="rework-reason" className="field" value={reviewReason} minLength={3} maxLength={500} required onChange={(event) => setReviewReason(event.target.value)} rows={3} /><Button disabled={mutation.isPending}>Request rework</Button></form></div>}
      {manager && workOrder.status === 'VERIFIED' && <Button disabled={mutation.isPending} onClick={() => send('close')}>Close work order</Button>}
      {manager && ['ASSIGNED', 'ACCEPTED', 'REWORK'].includes(workOrder.status) && <form className="work-order-form" onSubmit={(event) => { event.preventDefault(); send('cancel', { reason: cancelReason }) }}><h4>Cancel work order</h4><label htmlFor="cancel-reason">Reason</label><Input id="cancel-reason" minLength={3} maxLength={500} required value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} /><Button disabled={mutation.isPending}>Cancel task</Button></form>}
      {workOrder.created_by_name && <Info label="Created by" value={workOrder.created_by_name} />}{workOrder.verified_by_name && <Info label="Verified by" value={workOrder.verified_by_name} />}
    </aside></div>
    <div><Button onClick={() => navigate('/work-orders')}>Back to work orders</Button></div>
  </section>
}

function WorkOrderLifecycle({ status }: { status: WorkOrderStatus }) {
  const stages: { status: WorkOrderStatus; label: string }[] = [
    { status: 'ASSIGNED', label: 'Assigned' }, { status: 'ACCEPTED', label: 'Accepted' }, { status: 'IN_PROGRESS', label: 'In progress' },
    { status: 'COMPLETED', label: 'Awaiting verification' }, { status: 'VERIFIED', label: 'Verified' }, { status: 'CLOSED', label: 'Closed' },
  ]
  const active = status === 'REWORK' ? 2 : stages.findIndex((stage) => stage.status === status)
  return <ol className="work-order-lifecycle" aria-label={`Work-order lifecycle, current status: ${statusLabels[status]}`}>
    {stages.map((stage, index) => <li key={stage.status} className={index < active ? 'is-complete' : index === active ? 'is-current' : ''} aria-current={index === active ? 'step' : undefined}><span aria-hidden="true">{index < active ? '✓' : index + 1}</span><strong>{stage.label}</strong></li>)}
    {status === 'REWORK' && <li className="is-current lifecycle-rework" aria-current="step"><span aria-hidden="true">!</span><strong>Rework required</strong></li>}
  </ol>
}

export function IssueWorkOrdersSection({ issueId, assignedTeam, user }: { issueId: number; assignedTeam: number | null; user: AuthUser }) {
  const cache = useQueryClient()
  const navigate = useNavigate()
  const canView = user.role === 'TECHNICIAN' || managerRoles.has(user.role)
  const canCreate = managerRoles.has(user.role)
  const query = useQuery({ queryKey: ['issue-work-orders', issueId], queryFn: () => apiRequest<Paginated<WorkOrderRecord>>(`/issues/${issueId}/work-orders/`), enabled: canView })
  const teams = useQuery({ queryKey: ['teams'], queryFn: () => apiRequest<Paginated<TeamOption>>('/teams/'), enabled: canCreate })
  const allowedTeams = (teams.data?.results ?? []).filter((team) => team.is_active && (user.role !== 'SUPERVISOR' || user.team_ids.includes(team.id)))
  const initialTeam = assignedTeam && allowedTeams.some((team) => team.id === assignedTeam) ? String(assignedTeam) : ''
  const [team, setTeam] = useState(initialTeam)
  const [title, setTitle] = useState('')
  const [instructions, setInstructions] = useState('')
  const create = useMutation({
    mutationFn: (body: { team: number; title?: string; instructions: string }) => apiRequest<WorkOrderDetail>(`/issues/${issueId}/work-orders/`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (workOrder) => { void cache.invalidateQueries({ queryKey: ['issue-work-orders', issueId] }); refreshWorkOrders(cache); navigate(`/work-orders/${workOrder.id}`) },
  })
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); create.mutate({ team: Number(team), title: title.trim() || undefined, instructions }) }
  useEffect(() => { if (!team && initialTeam) setTeam(initialTeam) }, [team, initialTeam])
  if (!canView) return null
  return <section className="detail-section issue-work-orders"><div className="section-heading"><div><h3>Work orders</h3><p>Operational tasks linked to this issue.</p></div></div>
    {query.isPending ? <Loading label="Loading work orders" /> : query.isError ? <ErrorState title="Work orders unavailable" detail={errorMessage(query.error)} onRetry={() => { void query.refetch() }} /> : query.data.count ? <ul className="linked-work-orders">{query.data.results.map((workOrder) => <li key={workOrder.id}><Link to={`/work-orders/${workOrder.id}`}><strong>{workOrder.number}</strong><span>{workOrder.title}</span></Link><Badge tone={statusTone[workOrder.status]}>{statusLabels[workOrder.status]}</Badge></li>)}</ul> : <p className="muted-copy">No work order has been created for this issue.</p>}
    {canCreate && <details className="create-work-order"><summary>Create work order</summary>{teams.isPending ? <Loading label="Loading teams" /> : teams.isError ? <ErrorState title="Team list unavailable" detail={errorMessage(teams.error)} /> : <form className="work-order-form" onSubmit={submit}><label htmlFor={`create-team-${issueId}`}>Assigned team</label><Select id={`create-team-${issueId}`} required value={team} onChange={(event) => setTeam(event.target.value)}><option value="">Select a team</option>{allowedTeams.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}</Select><label htmlFor={`create-title-${issueId}`}>Task summary <span className="optional-mark">Defaults to issue title</span></label><Input id={`create-title-${issueId}`} maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} /><label htmlFor={`create-instructions-${issueId}`}>Field instructions</label><textarea id={`create-instructions-${issueId}`} className="field" rows={3} maxLength={5000} value={instructions} onChange={(event) => setInstructions(event.target.value)} /><Button variant="primary" disabled={create.isPending || !team}>{create.isPending ? 'Creating…' : 'Create work order'}</Button>{create.isError && <p className="form-error" role="alert">{errorMessage(create.error)}</p>}</form>}</details>}
  </section>
}

function Metric({ label, value }: { label: string; value: number }) { return <article><span>{label}</span><strong>{value.toLocaleString()}</strong></article> }
function Info({ label, value }: { label: string; value: string }) { return <div className="info-row"><span>{label}</span><strong>{value}</strong></div> }
