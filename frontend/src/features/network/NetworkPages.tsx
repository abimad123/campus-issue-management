import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, EmptyState, ErrorState, Input, Loading, Select } from '../../components/ui'
import { ApiError, apiRequest } from '../../lib/api'
import type { AuthUser, IssueNetworkContext, IssueRecord, LocationOption, NetworkConnectionState, NetworkDeviceKind, NetworkDeviceRecord, NetworkDeviceState, NetworkKind, NetworkMeasurementRecord, NetworkQualityEvaluation, NetworkRecord, Paginated } from '../../types/api'

const values = <T,>(page: Paginated<T> | undefined) => page?.results ?? []
const errorText = (error: unknown) => error instanceof ApiError ? error.message : 'Review the values and try again.'
const networkKindLabel: Record<NetworkKind, string> = { WIFI: 'Wi-Fi', LAN: 'LAN', WAN: 'WAN' }
const deviceKindLabel: Record<NetworkDeviceKind, string> = { ACCESS_POINT: 'Access point', SWITCH: 'Switch', ROUTER: 'Router', GATEWAY: 'Gateway' }
const deviceStateLabel: Record<NetworkDeviceState, string> = { DEPLOYED: 'Deployed', MAINTENANCE: 'Maintenance', RETIRED: 'Retired' }
const connectionLabel: Record<NetworkConnectionState, string> = { CONNECTED: 'Connected', DEGRADED: 'Degraded', DISCONNECTED: 'Disconnected', UNKNOWN: 'Unknown' }

export function NetworkDevicesPage({ canManage }: { canManage: boolean }) {
  const cache = useQueryClient()
  const devices = useQuery({ queryKey: ['network-devices'], queryFn: () => apiRequest<Paginated<NetworkDeviceRecord>>('/network-devices/') })
  const networks = useQuery({ queryKey: ['networks-options'], queryFn: () => apiRequest<Paginated<NetworkRecord>>('/networks/') })
  const locations = useQuery({ queryKey: ['network-locations'], queryFn: () => apiRequest<Paginated<LocationOption>>('/locations/') })
  const assets = useQuery({ queryKey: ['network-assets'], queryFn: () => apiRequest<Paginated<{ id: number; asset_code: string; name: string; location: number }>>('/assets/') })
  const mutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => apiRequest<NetworkDeviceRecord>('/network-devices/', { method: 'POST', body: JSON.stringify(payload) }),
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ['network-devices'] }) },
  })
  const isPending = devices.isPending || networks.isPending || locations.isPending || assets.isPending
  const isError = devices.isError || networks.isError || locations.isError || assets.isError
  if (isPending) return <div className="state-panel"><Loading label="Loading network inventory" /></div>
  if (isError) return <ErrorState title="Network inventory could not be loaded" detail="Check network, campus location, and asset services, then retry." onRetry={() => { void devices.refetch(); void networks.refetch(); void locations.refetch(); void assets.refetch() }} />
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    mutation.mutate({ device_code: data.get('device_code'), name: data.get('name'), kind: data.get('kind'), network: Number(data.get('network')), location: Number(data.get('location')), asset: data.get('asset') ? Number(data.get('asset')) : null, manufacturer: data.get('manufacturer'), model_number: data.get('model_number'), serial_number: data.get('serial_number'), state: data.get('state') })
  }
  const rows = devices.data?.results ?? []
  return <div className="network-page">
    <section className="content-section"><div className="section-heading"><div><h2>Network devices</h2><p>Inventory linked to registered campus networks and locations.</p></div></div>
      {rows.length ? <div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Device</th><th scope="col">Type</th><th scope="col">Network</th><th scope="col">Campus location</th><th scope="col">State</th></tr></thead><tbody>{rows.map((device) => <tr key={device.id}><td><Link className="text-link" to={`/network/devices/${device.id}`}><strong>{device.device_code}</strong><span className="table-subtitle">{device.name}</span></Link></td><td>{deviceKindLabel[device.kind]}</td><td>{device.network_name}</td><td>{device.location_name}</td><td><Badge tone={device.state === 'DEPLOYED' ? 'green' : device.state === 'MAINTENANCE' ? 'blue' : 'neutral'}>{deviceStateLabel[device.state]}</Badge></td></tr>)}</tbody></table></div> : <div className="state-panel"><EmptyState title="No network devices recorded" detail="Add inventory records here or register synthetic examples using the development seed command." /></div>}
    </section>
    {canManage && <form className="panel form-stack network-form" onSubmit={submit}><div className="panel-heading"><div><h2>Register a device</h2><p>Device location and linked asset must agree. Management credentials are not stored here.</p></div></div>
      <label>Device code<Input name="device_code" required maxLength={48} /></label><label>Device name<Input name="name" required maxLength={120} /></label>
      <label>Device type<Select name="kind" required defaultValue="ACCESS_POINT">{Object.entries(deviceKindLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label>
      <label>Network<Select name="network" required defaultValue=""><option value="">Choose a network</option>{values(networks.data).map((network) => <option key={network.id} value={network.id}>{network.name} · {networkKindLabel[network.kind]}</option>)}</Select></label>
      <label>Campus location<Select name="location" required defaultValue=""><option value="">Choose a location</option>{values(locations.data).map((location) => <option key={location.id} value={location.id}>{location.display_name}</option>)}</Select></label>
      <label>Linked asset (optional)<Select name="asset" defaultValue=""><option value="">No linked asset</option>{values(assets.data).map((asset) => <option key={asset.id} value={asset.id}>{asset.asset_code} · {asset.name}</option>)}</Select></label>
      <label>Manufacturer (optional)<Input name="manufacturer" maxLength={100} /></label><label>Model (optional)<Input name="model_number" maxLength={100} /></label><label>Serial number (optional)<Input name="serial_number" maxLength={100} /></label>
      <label>State<Select name="state" defaultValue="DEPLOYED">{Object.entries(deviceStateLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label>
      {mutation.isError && <p className="form-error" role="alert">Device could not be saved: {errorText(mutation.error)}</p>}{mutation.isSuccess && <p role="status">Network device registered.</p>}
      <Button variant="primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Register device'}</Button>
    </form>}
  </div>
}

export function NetworkDeviceDetailPage() {
  const { id } = useParams()
  const device = useQuery({ queryKey: ['network-device', id], queryFn: () => apiRequest<NetworkDeviceRecord>(`/network-devices/${id}/`) })
  const samples = useQuery({ queryKey: ['network-measurements', 'device', id], queryFn: () => apiRequest<Paginated<NetworkMeasurementRecord>>(`/network-measurements/?device=${id}`), enabled: Boolean(id) })
  if (device.isPending) return <div className="state-panel"><Loading label="Loading network device" /></div>
  if (device.isError) return <ErrorState title="Network device could not be loaded" detail="The record may have been removed or your access may have changed." onRetry={() => { void device.refetch() }} />
  const item = device.data
  return <div className="network-page"><section className="panel network-device-header"><div><p className="eyebrow">{deviceKindLabel[item.kind]} · {item.device_code}</p><h2>{item.name}</h2><p>{item.manufacturer || 'Manufacturer not recorded'}{item.model_number ? ` · ${item.model_number}` : ''}</p></div><Badge tone={item.state === 'DEPLOYED' ? 'green' : 'neutral'}>{deviceStateLabel[item.state]}</Badge></section>
    <section className="panel"><h2>Device record</h2><dl className="network-detail-grid"><div><dt>Network</dt><dd>{item.network_name} ({item.network_code})</dd></div><div><dt>Campus</dt><dd>{item.campus_name}</dd></div><div><dt>Location</dt><dd>{item.location_name}</dd></div><div><dt>Linked asset</dt><dd>{item.asset_code ?? 'No asset linked'}</dd></div><div><dt>Serial number</dt><dd>{item.serial_number || 'Not recorded'}</dd></div><div><dt>Inventory state</dt><dd>{deviceStateLabel[item.state]}</dd></div></dl></section>
    <section className="content-section"><div className="section-heading"><div><h2>Measurements for this device</h2><p>Raw readings with transparent per-record evaluations; no aggregate scores or trends.</p></div></div>{samples.isPending ? <div className="state-panel"><Loading label="Loading device measurements" /></div> : samples.isError ? <ErrorState title="Measurements could not be loaded" detail="Retry to reload measurement records." onRetry={() => { void samples.refetch() }} /> : samples.data.count === 0 ? <div className="state-panel"><EmptyState title="No measurements recorded" detail="Measurements for this device will appear after an authorized user submits them." /></div> : <MeasurementTable rows={samples.data.results} />}</section>
  </div>
}

export function NetworksPage({ canManage }: { canManage: boolean }) {
  const cache = useQueryClient()
  const networks = useQuery({ queryKey: ['networks'], queryFn: () => apiRequest<Paginated<NetworkRecord>>('/networks/') })
  const campuses = useQuery({ queryKey: ['campuses-network'], queryFn: () => apiRequest<Paginated<{ id: number; name: string }>>('/campuses/') })
  const buildings = useQuery({ queryKey: ['buildings-network'], queryFn: () => apiRequest<Paginated<{ id: number; name: string; campus: number; campus_name: string }>>('/buildings/') })
  const mutation = useMutation({ mutationFn: (payload: Record<string, unknown>) => apiRequest<NetworkRecord>('/networks/', { method: 'POST', body: JSON.stringify(payload) }), onSuccess: () => { void cache.invalidateQueries({ queryKey: ['networks'] }) } })
  const isPending = networks.isPending || campuses.isPending || buildings.isPending
  const isError = networks.isError || campuses.isError || buildings.isError
  if (isPending) return <div className="state-panel"><Loading label="Loading networks" /></div>
  if (isError) return <ErrorState title="Networks could not be loaded" detail="Check campus reference data and retry." onRetry={() => { void networks.refetch(); void campuses.refetch(); void buildings.refetch() }} />
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    mutation.mutate({ campus: Number(data.get('campus')), building: data.get('building') ? Number(data.get('building')) : null, code: data.get('code'), name: data.get('name'), kind: data.get('kind'), description: data.get('description'), is_active: data.get('is_active') === 'true' })
  }
  const rows = networks.data?.results ?? []
  return <div className="network-page"><section className="content-section"><div className="section-heading"><div><h2>Networks</h2><p>Campus network inventory by Wi-Fi, LAN, and WAN type.</p></div></div>{rows.length ? <div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Network</th><th scope="col">Type</th><th scope="col">Campus</th><th scope="col">Building scope</th><th scope="col">State</th></tr></thead><tbody>{rows.map((network) => <tr key={network.id}><td><strong>{network.name}</strong><span className="table-subtitle">{network.code}</span></td><td>{networkKindLabel[network.kind]}</td><td>{network.campus_name}</td><td>{network.building_name ?? 'Campus-wide'}</td><td><Badge tone={network.is_active ? 'green' : 'neutral'}>{network.is_active ? 'Active' : 'Inactive'}</Badge></td></tr>)}</tbody></table></div> : <div className="state-panel"><EmptyState title="No networks registered" detail="Register campus Wi-Fi, LAN, and WAN networks to associate devices and measurements." /></div>}</section>
    {canManage && <form className="panel form-stack network-form" onSubmit={submit}><div className="panel-heading"><div><h2>Register a network</h2><p>Attach a network to a campus and, when applicable, one building.</p></div></div>
      <label>Campus<Select name="campus" required defaultValue=""><option value="">Choose a campus</option>{values(campuses.data).map((campus) => <option key={campus.id} value={campus.id}>{campus.name}</option>)}</Select></label><label>Building (optional)<Select name="building" defaultValue=""><option value="">Campus-wide</option>{values(buildings.data).map((building) => <option key={building.id} value={building.id}>{building.campus_name} · {building.name}</option>)}</Select></label>
      <label>Network code<Input name="code" required maxLength={32} pattern="[A-Za-z0-9_-]+" /></label><label>Network name<Input name="name" required maxLength={120} /></label><label>Network type<Select name="kind" required defaultValue="WIFI">{Object.entries(networkKindLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label><label>Description (optional)<Input name="description" maxLength={500} /></label><label>State<Select name="is_active" defaultValue="true"><option value="true">Active</option><option value="false">Inactive</option></Select></label>
      {mutation.isError && <p className="form-error" role="alert">Network could not be saved: {errorText(mutation.error)}</p>}{mutation.isSuccess && <p role="status">Network registered.</p>}<Button variant="primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Register network'}</Button>
    </form>}
  </div>
}

export function NetworkMeasurementsPage() {
  const cache = useQueryClient()
  const [networkFilter, setNetworkFilter] = useState('')
  const queryString = networkFilter ? `?network=${networkFilter}` : ''
  const measurements = useQuery({ queryKey: ['network-measurements', networkFilter], queryFn: () => apiRequest<Paginated<NetworkMeasurementRecord>>(`/network-measurements/${queryString}`) })
  const networks = useQuery({ queryKey: ['networks-options'], queryFn: () => apiRequest<Paginated<NetworkRecord>>('/networks/') })
  const locations = useQuery({ queryKey: ['network-locations'], queryFn: () => apiRequest<Paginated<LocationOption>>('/locations/') })
  const devices = useQuery({ queryKey: ['network-devices-options'], queryFn: () => apiRequest<Paginated<NetworkDeviceRecord>>('/network-devices/') })
  const mutation = useMutation({ mutationFn: (payload: Record<string, unknown>) => apiRequest<NetworkMeasurementRecord>('/network-measurements/', { method: 'POST', body: JSON.stringify(payload) }), onSuccess: () => { void cache.invalidateQueries({ queryKey: ['network-measurements'] }) } })
  const busy = measurements.isPending || networks.isPending || locations.isPending || devices.isPending
  const failed = measurements.isError || networks.isError || locations.isError || devices.isError
  if (busy) return <div className="state-panel"><Loading label="Loading raw measurements" /></div>
  if (failed) return <ErrorState title="Measurements could not be loaded" detail="Check the network inventory and retry." onRetry={() => { void measurements.refetch(); void networks.refetch(); void locations.refetch(); void devices.refetch() }} />
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    const numeric = (key: string) => data.get(key) ? Number(data.get(key)) : null
    mutation.mutate({ network: Number(data.get('network')), location: Number(data.get('location')), device: data.get('device') ? Number(data.get('device')) : null, latency_ms: numeric('latency_ms'), packet_loss_percent: numeric('packet_loss_percent'), download_mbps: numeric('download_mbps'), upload_mbps: numeric('upload_mbps'), signal_strength_dbm: numeric('signal_strength_dbm'), connection_state: data.get('connection_state'), note: data.get('note') })
  }
  const rows = measurements.data?.results ?? []
  return <div className="network-page"><section className="content-section"><div className="section-heading network-measurement-heading"><div><h2>Measurement quality</h2><p>Versioned, explainable evaluation of each submitted observation; source readings remain unchanged.</p></div><label>Network filter<Select value={networkFilter} onChange={(event) => setNetworkFilter(event.target.value)}><option value="">All networks</option>{values(networks.data).map((network) => <option key={network.id} value={network.id}>{network.name}</option>)}</Select></label></div>{rows.length ? <MeasurementTable rows={rows} /> : <div className="state-panel"><EmptyState title="No measurements recorded" detail="Record a measurement to begin evaluating submitted network observations." /></div>}</section>
    <form className="panel form-stack network-form" onSubmit={submit}><div className="panel-heading"><div><h2>Record a measurement</h2><p>Values are user-submitted observations, not active infrastructure polling.</p></div></div>
      <label>Network<Select name="network" required defaultValue=""><option value="">Choose a network</option>{values(networks.data).map((network) => <option key={network.id} value={network.id}>{network.name} · {networkKindLabel[network.kind]}</option>)}</Select></label><label>Campus location<Select name="location" required defaultValue=""><option value="">Choose a location</option>{values(locations.data).map((location) => <option key={location.id} value={location.id}>{location.display_name}</option>)}</Select></label><label>Device (optional)<Select name="device" defaultValue=""><option value="">No specific device</option>{values(devices.data).map((device) => <option key={device.id} value={device.id}>{device.device_code} · {device.name}</option>)}</Select></label>
      <div className="network-reading-grid"><label>Latency (ms)<Input name="latency_ms" type="number" min="0" max="60000" step="0.01" /></label><label>Packet loss (%)<Input name="packet_loss_percent" type="number" min="0" max="100" step="0.01" /></label><label>Download (Mbps)<Input name="download_mbps" type="number" min="0" max="1000000" step="0.001" /></label><label>Upload (Mbps)<Input name="upload_mbps" type="number" min="0" max="1000000" step="0.001" /></label><label>Signal (dBm)<Input name="signal_strength_dbm" type="number" min="-120" max="0" step="1" /></label></div>
      <label>Connection state<Select name="connection_state" defaultValue="UNKNOWN">{Object.entries(connectionLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label><label>Note (optional)<Input name="note" maxLength={240} /></label>
      {mutation.isError && <p className="form-error" role="alert">Measurement was not saved: {errorText(mutation.error)}</p>}{mutation.isSuccess && <p role="status">Raw measurement recorded.</p>}<Button variant="primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Record measurement'}</Button>
    </form>
  </div>
}

export function NetworkMeasurementEvaluationPage({ user }: { user: AuthUser }) {
  const { id } = useParams()
  const evaluation = useQuery({ queryKey: ['network-measurement-evaluation', id], queryFn: () => apiRequest<NetworkQualityEvaluation>(`/network-measurements/${id}/evaluation/`), enabled: Boolean(id) })
  if (evaluation.isPending) return <div className="state-panel"><Loading label="Evaluating network measurement" /></div>
  if (evaluation.isError) return <ErrorState title="Measurement evaluation could not be loaded" detail="The measurement may have been removed or your access may have changed." onRetry={() => { void evaluation.refetch() }} />
  const item = evaluation.data
  return <div className="network-page"><p><Link className="text-link" to="/network/measurements">← Measurements</Link></p><section className="panel quality-summary"><div><p className="eyebrow">Measurement #{item.measurement.id} · Evaluation {item.evaluation_version}</p><h2>{item.overall_label}</h2><p>{item.measurement.network_name} · {item.measurement.location_name} · <time dateTime={item.measurement.measured_at}>{new Date(item.measurement.measured_at).toLocaleString()}</time></p></div><QualityBadge quality={item.overall_quality} /></section>
    <NetworkContextActions evaluation={item} user={user} />
    <section className="panel"><h2>Evaluation details</h2>{item.primary_factor_label ? <p><strong>Primary factor:</strong> {item.primary_factor_label}{item.reasons.length ? ` — ${item.reasons[0]}` : ''}</p> : <p>This result cannot be classified because no numeric measurements are available.</p>}<div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Metric</th><th scope="col">Recorded value</th><th scope="col">Evaluation</th><th scope="col">Explanation</th></tr></thead><tbody>{item.metrics.map((metric) => <tr key={metric.key}><th scope="row">{metric.label}</th><td>{metric.value === null ? 'Not recorded' : `${metric.value}${metric.unit ? ` ${metric.unit}` : ''}`}</td><td>{metric.quality ? <QualityBadge quality={metric.quality} /> : metric.status === 'CONNECTED' ? 'Connected' : metric.status === 'UNKNOWN' || metric.status === 'UNAVAILABLE' ? 'Unavailable' : metric.status}</td><td>{metric.reason}</td></tr>)}</tbody></table></div></section>
  </div>
}

function NetworkContextActions({ evaluation, user }: { evaluation: NetworkQualityEvaluation; user: AuthUser }) {
  const cache = useQueryClient()
  const canAttach = user.role === 'ADMIN' || (user.role === 'TECHNICAL_STAFF' && ['network', 'it support'].includes(user.technical_specialization.trim().toLowerCase()))
  const [attachOpen, setAttachOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedIssue, setSelectedIssue] = useState('')
  const [attachedIssueId, setAttachedIssueId] = useState<number | null>(null)
  const query = new URLSearchParams({ page: String(page) })
  if (search.trim()) query.set('search', search.trim())
  const issues = useQuery({
    queryKey: ['network-context-issues', evaluation.measurement.id, search, page],
    queryFn: () => apiRequest<Paginated<IssueRecord>>(`/issues/?${query.toString()}`),
    enabled: attachOpen && canAttach,
  })
  const attach = useMutation({
    mutationFn: () => apiRequest<IssueNetworkContext>(`/issues/${selectedIssue}/network-context/`, {
      method: 'POST',
      body: JSON.stringify({ network_measurement: evaluation.measurement.id }),
    }),
    onSuccess: (context) => {
      setAttachedIssueId(context.issue)
      setSelectedIssue('')
      void cache.invalidateQueries({ queryKey: ['issue-network-context', context.issue] })
    },
  })
  const manageableIssues = (issues.data?.results ?? []).filter((issue) => user.role !== 'ADMIN'
    || (issue.assigned_team !== null && user.team_ids.includes(issue.assigned_team)))
  const pageCount = Math.max(1, Math.ceil((issues.data?.count ?? 0) / 20))
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (selectedIssue) attach.mutate()
  }
  return <section className="panel network-context-actions" aria-label="Create or attach a campus issue">
    <div className="panel-heading"><div><h2>Use this network finding</h2><p>Operator-assisted only. Network readings support the issue record; they do not create issues automatically.</p></div></div>
    <div className="form-actions"><Link className="button button--primary" to={`/issues/new?network_measurement=${evaluation.measurement.id}`}>Create Issue</Link>
      {canAttach && <Button type="button" onClick={() => setAttachOpen((open) => !open)}>{attachOpen ? 'Close issue search' : 'Attach to Existing Issue'}</Button>}</div>
    {attachedIssueId && <p role="status">Network evidence attached to <Link className="text-link" to={`/issues/${attachedIssueId}`}>issue #{attachedIssueId}</Link>.</p>}
    {attachOpen && canAttach && <form className="form-stack network-attach-form" onSubmit={submit}>
      <label htmlFor="network-context-search">Search issues you can manage<Input id="network-context-search" type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); setSelectedIssue('') }} placeholder="Ticket number, title, description, or location" /></label>
      {issues.isPending ? <Loading label="Loading manageable issues" />
        : issues.isError ? <ErrorState title="Issues could not be loaded" detail={issues.error instanceof ApiError ? issues.error.message : 'Retry to load issues in your scope.'} onRetry={() => { void issues.refetch() }} />
          : manageableIssues.length === 0 ? <EmptyState title="No manageable issues on this page" detail="Try another search or review another page. Issues outside your existing permissions are not listed." />
            : <label htmlFor="network-context-issue">Choose an issue<Select id="network-context-issue" value={selectedIssue} onChange={(event) => setSelectedIssue(event.target.value)} required><option value="">Select an issue</option>{manageableIssues.map((issue) => <option key={issue.id} value={issue.id}>{issue.ticket_number} · {issue.title} · {issue.status.replace(/_/g, ' ')} · {issue.location_name} · {new Date(issue.created_at).toLocaleDateString()}</option>)}</Select></label>}
      {issues.data && <div className="pagination-bar"><span>{issues.data.count} visible issues · page {page} of {pageCount}</span><div><Button type="button" disabled={!issues.data.previous} onClick={() => { setPage((current) => current - 1); setSelectedIssue('') }}>Previous</Button><Button type="button" disabled={!issues.data.next} onClick={() => { setPage((current) => current + 1); setSelectedIssue('') }}>Next</Button></div></div>}
      {attach.isError && <p className="form-error" role="alert">Network context was not attached: {attach.error instanceof ApiError ? attach.error.message : 'Review access and try again.'}</p>}
      <Button variant="primary" type="submit" disabled={!selectedIssue || attach.isPending || issues.isPending}>{attach.isPending ? 'Attaching…' : 'Attach evidence'}</Button>
    </form>}
  </section>
}

function QualityBadge({ quality }: { quality: string }) {
  return <span className={`quality-badge quality-badge--${quality.toLowerCase()}`}>{quality.replace(/_/g, ' ')}</span>
}

function MeasurementTable({ rows }: { rows: NetworkMeasurementRecord[] }) {
  return <div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Measured</th><th scope="col">Network / location</th><th scope="col">Device</th><th scope="col">Latency</th><th scope="col">Packet loss</th><th scope="col">Download</th><th scope="col">Upload</th><th scope="col">Signal</th><th scope="col">Connection</th><th scope="col">Quality</th></tr></thead><tbody>{rows.map((measurement) => <tr key={measurement.id}><td><time dateTime={measurement.measured_at}>{new Date(measurement.measured_at).toLocaleString()}</time></td><td>{measurement.network_name}<span className="table-subtitle">{measurement.location_name}</span></td><td>{measurement.device_code ?? '—'}</td><td>{measurement.latency_ms !== null ? `${measurement.latency_ms} ms` : '—'}</td><td>{measurement.packet_loss_percent !== null ? `${measurement.packet_loss_percent}%` : '—'}</td><td>{measurement.download_mbps !== null ? `${measurement.download_mbps} Mbps` : '—'}</td><td>{measurement.upload_mbps !== null ? `${measurement.upload_mbps} Mbps` : '—'}</td><td>{measurement.signal_strength_dbm ?? '—'}{measurement.signal_strength_dbm !== null ? ' dBm' : ''}</td><td><Badge tone={measurement.connection_state === 'CONNECTED' ? 'green' : measurement.connection_state === 'DEGRADED' ? 'blue' : 'neutral'}>{connectionLabel[measurement.connection_state]}</Badge></td><td><Link className="text-link" to={`/network/measurements/${measurement.id}`}><QualityBadge quality={measurement.quality_evaluation.overall_quality} /><span className="table-subtitle">View evaluation</span></Link></td></tr>)}</tbody></table></div>
}
