import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiRequest } from '../../lib/api'
import { Button, EmptyState, ErrorState, Input, Loading, Select } from '../../components/ui'
import type { IssueCategory, IssuePriority, LocationOption, Paginated } from '../../types/api'

type TeamOption = { id: number; name: string; is_active: boolean }
type RoutingRule = { id: number; name: string; active: boolean; priority_order: number; category: number | null; category_name: string | null; location: number | null; location_name: string | null; issue_priority: IssuePriority | null; target_team: number; target_team_name: string; target_user: number | null }
type Escalation = { level: number; after_breach_seconds: number; recipient_role: string }
type SlaPolicy = { id: number; name: string; active: boolean; priority_order: number; category: number | null; category_name: string | null; issue_priority: IssuePriority | null; response_time_seconds: number; resolution_time_seconds: number; warning_before_seconds: number; escalation_levels: Escalation[] }
const priorities: IssuePriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const roles = ['SUPERVISOR', 'FACILITY_MANAGER', 'IT_MANAGER', 'CAMPUS_ADMIN', 'SYSTEM_ADMIN']
const labels: Record<string, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' }
const list = <T,>(data: Paginated<T> | T[] | undefined): T[] => Array.isArray(data) ? data : data?.results ?? []
const message = (error: unknown) => error instanceof ApiError ? error.message : 'Check the form and try again.'

export function RoutingRulesPage() {
  const cache = useQueryClient()
  const rulesQ = useQuery({ queryKey: ['routing-rules'], queryFn: () => apiRequest<Paginated<RoutingRule>>('/admin/routing-rules/') })
  const categoriesQ = useQuery({ queryKey: ['issue-categories'], queryFn: () => apiRequest<Paginated<IssueCategory>>('/issue-categories/') })
  const locationsQ = useQuery({ queryKey: ['locations'], queryFn: () => apiRequest<Paginated<LocationOption>>('/locations/') })
  const teamsQ = useQuery({ queryKey: ['teams'], queryFn: () => apiRequest<Paginated<TeamOption>>('/teams/') })
  const [selected, setSelected] = useState<number | ''>('')
  const rule = list(rulesQ.data).find((entry) => entry.id === selected)
  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiRequest<RoutingRule>(selected ? `/admin/routing-rules/${selected}/` : '/admin/routing-rules/', { method: selected ? 'PATCH' : 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ['routing-rules'] }) },
  })
  const categories = list(categoriesQ.data); const locations = list(locationsQ.data); const teams = list(teamsQ.data).filter((team) => team.is_active)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    mutation.mutate({ name: data.get('name'), active: data.get('active') === 'true', priority_order: Number(data.get('order')), category: data.get('category') ? Number(data.get('category')) : null, location: data.get('location') ? Number(data.get('location')) : null, issue_priority: data.get('priority') || null, target_team: Number(data.get('team')) })
  }
  if (rulesQ.isPending || categoriesQ.isPending || locationsQ.isPending || teamsQ.isPending) return <div className="state-panel"><Loading label="Loading routing configuration" /></div>
  if (rulesQ.isError || categoriesQ.isError || locationsQ.isError || teamsQ.isError) return <ErrorState title="Routing configuration could not be loaded" />
  return <div className="config-layout"><section className="panel"><div className="panel-heading"><div><h2>Routing rules</h2><p>More specific conditions take precedence, then lower order, then stable record ID.</p></div></div>{list(rulesQ.data).length ? <div className="table-wrap"><table><thead><tr><th>Rule</th><th>Conditions</th><th>Target team</th><th>Order</th><th>State</th></tr></thead><tbody>{list(rulesQ.data).map((item) => <tr key={item.id}><td><button className="text-button" onClick={() => setSelected(item.id)}>{item.name}</button></td><td>{[item.category_name, item.location_name, item.issue_priority ? labels[item.issue_priority] : null].filter(Boolean).join(' · ') || 'Any issue'}</td><td>{item.target_team_name}</td><td>{item.priority_order}</td><td>{item.active ? 'Active' : 'Inactive'}</td></tr>)}</tbody></table></div> : <EmptyState title="No routing rules yet" detail="Create a rule to route matching issues automatically." />}</section>
    <form className="panel form-stack" onSubmit={submit}><div className="panel-heading"><div><h2>{selected ? 'Edit routing rule' : 'New routing rule'}</h2><p>Conditions are combined with AND. Leave a condition empty to match any value.</p></div></div>
      <label>Existing rule<Select value={selected} onChange={(e) => setSelected(e.target.value ? Number(e.target.value) : '')}><option value="">Create new</option>{list(rulesQ.data).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label>
      <RuleFields key={selected || 'new'} rule={rule} categories={categories} locations={locations} teams={teams} />
      {mutation.isError && <p className="form-error" role="alert">{message(mutation.error)}</p>}{mutation.isSuccess && <p role="status">Routing rule saved.</p>}
      <div className="form-actions"><Button type="button" onClick={() => setSelected('')}>New rule</Button><Button variant="primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save rule'}</Button></div>
      <RulePreview rule={rule} />
    </form></div>
}

function RuleFields({ rule, categories, locations, teams }: { rule?: RoutingRule; categories: IssueCategory[]; locations: LocationOption[]; teams: TeamOption[] }) {
  return <>
    <label>Rule name<Input name="name" required defaultValue={rule?.name ?? ''} maxLength={120} /></label>
    <label>Order<Input type="number" name="order" min="0" required defaultValue={rule?.priority_order ?? 100} /></label>
    <label>Category<Select name="category" defaultValue={rule?.category ?? ''}><option value="">Any category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label>
    <label>Location<Select name="location" defaultValue={rule?.location ?? ''}><option value="">Any location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</Select></label>
    <label>Priority<Select name="priority" defaultValue={rule?.issue_priority ?? ''}><option value="">Any priority</option>{priorities.map((item) => <option key={item} value={item}>{labels[item]}</option>)}</Select></label>
    <label>Target team<Select name="team" defaultValue={rule?.target_team ?? ''} required><option value="">Select a team</option>{teams.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label>
    <label>Rule state<Select name="active" defaultValue={String(rule?.active ?? true)}><option value="true">Enabled</option><option value="false">Disabled</option></Select></label>
  </>
}

function RulePreview({ rule }: { rule?: RoutingRule }) {
  return <div className="rule-preview"><strong>Rule preview</strong><p>IF Category = {rule?.category_name ?? 'Any'} AND Location = {rule?.location_name ?? 'Any'} AND Priority = {rule?.issue_priority ? labels[rule.issue_priority] : 'Any'}</p><p>THEN Assign team = {rule?.target_team_name ?? 'Selected team'}</p></div>
}

export function SlaPoliciesPage() {
  const cache = useQueryClient()
  const policiesQ = useQuery({ queryKey: ['sla-policies'], queryFn: () => apiRequest<Paginated<SlaPolicy>>('/admin/sla-policies/') })
  const categoriesQ = useQuery({ queryKey: ['issue-categories'], queryFn: () => apiRequest<Paginated<IssueCategory>>('/issue-categories/') })
  const [selected, setSelected] = useState<number | ''>('')
  const policy = list(policiesQ.data).find((entry) => entry.id === selected)
  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => apiRequest<SlaPolicy>(selected ? `/admin/sla-policies/${selected}/` : '/admin/sla-policies/', { method: selected ? 'PATCH' : 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ['sla-policies'] }) },
  })
  const categories = list(categoriesQ.data)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    const escalation_levels = [1, 2, 3].flatMap((level) => {
      const recipient_role = String(data.get(`role_${level}`) || '')
      return recipient_role ? [{ level, after_breach_seconds: Number(data.get(`after_minutes_${level}`) || 0) * 60, recipient_role }] : []
    })
    mutation.mutate({ name: data.get('name'), active: data.get('active') === 'true', priority_order: Number(data.get('order')), category: data.get('category') ? Number(data.get('category')) : null, issue_priority: data.get('priority') || null, response_time_seconds: Number(data.get('response_minutes')) * 60, resolution_time_seconds: Number(data.get('resolution_minutes')) * 60, warning_before_seconds: Number(data.get('warning_minutes')) * 60, escalation_levels })
  }
  if (policiesQ.isPending || categoriesQ.isPending) return <div className="state-panel"><Loading label="Loading SLA policies" /></div>
  if (policiesQ.isError || categoriesQ.isError) return <ErrorState title="SLA policies could not be loaded" />
  return <div className="config-layout"><section className="panel"><div className="panel-heading"><div><h2>SLA policies</h2><p>Most-specific match takes precedence, then lower order, then record ID.</p></div></div>{list(policiesQ.data).length ? <div className="table-wrap"><table><thead><tr><th>Policy</th><th>Applies to</th><th>Response</th><th>Resolution</th><th>State</th></tr></thead><tbody>{list(policiesQ.data).map((item) => <tr key={item.id}><td><button className="text-button" onClick={() => setSelected(item.id)}>{item.name}</button></td><td>{[item.category_name, item.issue_priority ? labels[item.issue_priority] : null].filter(Boolean).join(' · ') || 'Default'}</td><td>{minutes(item.response_time_seconds)}</td><td>{minutes(item.resolution_time_seconds)}</td><td>{item.active ? 'Active' : 'Inactive'}</td></tr>)}</tbody></table></div> : <EmptyState title="No SLA policies yet" detail="Add a default policy or a more specific category/priority policy." />}</section>
    <form className="panel form-stack" onSubmit={submit}><div className="panel-heading"><div><h2>{selected ? 'Edit SLA policy' : 'New SLA policy'}</h2><p>Times are entered in minutes. A policy with both conditions empty is the default.</p></div></div>
      <label>Existing policy<Select value={selected} onChange={(e) => setSelected(e.target.value ? Number(e.target.value) : '')}><option value="">Create new</option>{list(policiesQ.data).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label>
      <PolicyFields key={selected || 'new'} policy={policy} categories={categories} />
      {mutation.isError && <p className="form-error" role="alert">{message(mutation.error)}</p>}{mutation.isSuccess && <p role="status">SLA policy saved.</p>}
      <div className="form-actions"><Button type="button" onClick={() => setSelected('')}>New policy</Button><Button variant="primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save policy'}</Button></div>
    </form></div>
}

function PolicyFields({ policy, categories }: { policy?: SlaPolicy; categories: IssueCategory[] }) {
  const response = minutes(policy?.response_time_seconds ?? 1800)
  const resolution = minutes(policy?.resolution_time_seconds ?? 14400)
  const warning = minutes(policy?.warning_before_seconds ?? 1800)
  return <>
    <label>Policy name<Input name="name" required maxLength={120} defaultValue={policy?.name ?? ''} /></label>
    <label>Order<Input type="number" name="order" min="0" defaultValue={policy?.priority_order ?? 100} /></label>
    <label>Category<Select name="category" defaultValue={policy?.category ?? ''}><option value="">Any category (default)</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></label>
    <label>Priority<Select name="priority" defaultValue={policy?.issue_priority ?? ''}><option value="">Any priority</option>{priorities.map((item) => <option key={item} value={item}>{labels[item]}</option>)}</Select></label>
    <label>Response time (minutes)<Input type="number" name="response_minutes" min="1" required defaultValue={response} /></label>
    <label>Resolution time (minutes)<Input type="number" name="resolution_minutes" min="1" required defaultValue={resolution} /></label>
    <label>Warning before deadline (minutes)<Input type="number" name="warning_minutes" min="0" required defaultValue={warning} /></label>
    {[1, 2, 3].map((level) => {
      const escalation = policy?.escalation_levels?.find((item) => item.level === level)
      return <div className="form-row" key={level}><label>Escalation level {level}<Select name={`role_${level}`} defaultValue={escalation?.recipient_role ?? ''}><option value="">No level</option>{roles.map((role) => <option key={role} value={role}>{role.replace(/_/g, ' ')}</option>)}</Select></label><label>Minutes after first breach<Input type="number" name={`after_minutes_${level}`} min="0" defaultValue={minutes(escalation?.after_breach_seconds ?? 0)} /></label></div>
    })}
    <label>Policy state<Select name="active" defaultValue={String(policy?.active ?? true)}><option value="true">Enabled</option><option value="false">Disabled</option></Select></label>
  </>
}

function minutes(seconds: number) { return Math.max(0, Math.round(seconds / 60)) }
