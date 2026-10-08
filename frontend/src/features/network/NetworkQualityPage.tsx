import { useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, EmptyState, ErrorState, Loading, Select } from '../../components/ui'
import { apiRequest } from '../../lib/api'
import type { AnalyticsFactor, AnalyticsGroup, AnalyticsPage, NetworkAnalyticsSummary, NetworkMeasurementRecord } from '../../types/api'
import NetworkQualityTrends from './NetworkQualityTrends'

type Filters = { range: '24h' | '7d' | '30d'; campus: string; building: string; location: string; network: string; device: string; device_type: string; network_type: string; quality: string; connection_state: string }
const initialFilters: Filters = { range: '24h', campus: '', building: '', location: '', network: '', device: '', device_type: '', network_type: '', quality: '', connection_state: '' }
const qualities = ['EXCELLENT', 'GOOD', 'FAIR', 'POOR', 'CRITICAL', 'INSUFFICIENT_DATA'] as const
const qualityTone = (quality: string): 'green' | 'blue' | 'red' | 'neutral' => quality === 'EXCELLENT' || quality === 'GOOD' ? 'green' : quality === 'FAIR' ? 'blue' : quality === 'POOR' || quality === 'CRITICAL' ? 'red' : 'neutral'
const label = (value: string) => value.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (letter: string) => letter.toUpperCase())
const dateTime = (value: string | null | undefined) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'No measurement'
const queryPath = (endpoint: string, filters: Filters, page?: number) => {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value)
  if (page && page > 1) params.set('page', String(page))
  return `${endpoint}?${params.toString()}`
}

export default function NetworkQualityPage() {
  const [filters, setFilters] = useState(initialFilters)
  const [pages, setPages] = useState<Record<string, number>>({})
  const queryClient = useQueryClient()
  const params = useMemo(() => queryPath('/network-analytics/summary/', filters), [filters])
  const summary = useQuery({ queryKey: ['network-quality', 'summary', params], queryFn: () => apiRequest<NetworkAnalyticsSummary>(params) })
  const locations = useGroupQuery('locations', '/network-analytics/locations/', filters, pages.locations ?? 1)
  const buildings = useGroupQuery('buildings', '/network-analytics/buildings/', filters, pages.buildings ?? 1)
  const devices = useGroupQuery('devices', '/network-analytics/devices/', filters, pages.devices ?? 1)
  const networks = useGroupQuery('networks', '/network-analytics/networks/', filters, pages.networks ?? 1)
  const problemLocations = useGroupQuery('problem-locations', '/network-analytics/problem-locations/', filters, pages['problem-locations'] ?? 1)
  const problemDevices = useGroupQuery('problem-devices', '/network-analytics/problem-devices/', filters, pages['problem-devices'] ?? 1)
  const campuses = useGroupQuery('campuses', '/network-analytics/campuses/', filters, pages.campuses ?? 1)
  const factors = useQuery({ queryKey: ['network-quality', 'factors', filters, pages.factors ?? 1], queryFn: () => apiRequest<AnalyticsPage<AnalyticsFactor>>(queryPath('/network-analytics/factors/', filters, pages.factors ?? 1)) })
  const latestWindow = summary.data?.window
  const recentFiltersSupported = !filters.campus && !filters.building && !filters.device_type && !filters.network_type && !filters.quality
  const recentPath = latestWindow && recentFiltersSupported ? `/network-measurements/?${new URLSearchParams({ measured_after: latestWindow.start, measured_before: latestWindow.end, ...(filters.network ? { network: filters.network } : {}), ...(filters.location ? { location: filters.location } : {}), ...(filters.device ? { device: filters.device } : {}), ...(filters.connection_state ? { connection_state: filters.connection_state } : {}), page: String(pages.recent ?? 1) })}` : ''
  const recent = useQuery({ queryKey: ['network-quality', 'recent', latestWindow, filters, pages.recent ?? 1], queryFn: () => apiRequest<{ count: number; next: string | null; previous: string | null; results: NetworkMeasurementRecord[] }>(recentPath), enabled: Boolean(recentPath) })

  function changeFilter(key: keyof Filters, value: string) { setFilters((current) => ({ ...current, [key]: value })); setPages({}) }
  function clearFilters() { setFilters(initialFilters); setPages({}) }
  const hasFilters = Object.entries(filters).some(([key, value]) => key !== 'range' && value)
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ['network-quality'] }) }

  return <div className="network-quality-page">
    <div className="network-quality-intro"><p>Derived from recorded measurements using the version {summary.data?.evaluation_version ?? '1.0'} evaluation. This is not live infrastructure monitoring.</p><Button onClick={refresh}>Refresh data</Button></div>
    <section className="content-section quality-filters" aria-label="Network quality filters">
      <div className="quality-filter-primary">
        <label>Time range<Select value={filters.range} onChange={(event) => changeFilter('range', event.target.value as Filters['range'])}><option value="24h">Last 24 hours</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option></Select></label>
        <label>Campus ID<input className="field" inputMode="numeric" type="number" min="1" value={filters.campus} onChange={(event) => changeFilter('campus', event.target.value)} placeholder="Any campus" /></label>
        <label>Building ID<input className="field" inputMode="numeric" type="number" min="1" value={filters.building} onChange={(event) => changeFilter('building', event.target.value)} placeholder="Any building" /></label>
        <details className="quality-advanced"><summary>More filters</summary><div className="quality-filter-advanced">
          <IdFilter title="Location ID" value={filters.location} onChange={(value) => changeFilter('location', value)} />
          <IdFilter title="Network ID" value={filters.network} onChange={(value) => changeFilter('network', value)} />
          <IdFilter title="Device ID" value={filters.device} onChange={(value) => changeFilter('device', value)} />
          <label>Device type<Select value={filters.device_type} onChange={(event) => changeFilter('device_type', event.target.value)}><option value="">Any device type</option>{['ACCESS_POINT', 'SWITCH', 'ROUTER', 'GATEWAY'].map((value) => <option key={value} value={value}>{label(value)}</option>)}</Select></label>
          <label>Network type<Select value={filters.network_type} onChange={(event) => changeFilter('network_type', event.target.value)}><option value="">Any network type</option>{['WIFI', 'LAN', 'WAN'].map((value) => <option key={value} value={value}>{label(value)}</option>)}</Select></label>
          <label>Quality<Select value={filters.quality} onChange={(event) => changeFilter('quality', event.target.value)}><option value="">Any quality</option>{qualities.map((value) => <option key={value} value={value}>{label(value)}</option>)}</Select></label>
          <label>Connection state<Select value={filters.connection_state} onChange={(event) => changeFilter('connection_state', event.target.value)}><option value="">Any state</option>{['CONNECTED', 'DEGRADED', 'DISCONNECTED', 'UNKNOWN'].map((value) => <option key={value} value={value}>{label(value)}</option>)}</Select></label>
        </div></details>
        {hasFilters && <Button className="quality-clear" onClick={clearFilters}>Clear filters</Button>}
      </div>
      {summary.data?.window && <p className="quality-window">Showing {dateTime(summary.data.window.start)} to {dateTime(summary.data.window.end)} · {summary.data.window.timezone}</p>}
    </section>

    {summary.isPending ? <div className="state-panel"><Loading label="Loading network quality summary" /></div> : summary.isError ? <ErrorState title="Network quality summary could not be loaded" detail="Your access may have changed, or the analytics service may be unavailable." onRetry={() => { void summary.refetch() }} /> : <>
      <section className="quality-overview" aria-label="Quality overview">
        <SummaryMetric title="Measurements" value={summary.data.total_measurements} />
        <SummaryMetric title="Overall quality" value={<QualityBadge quality={summary.data.overall_quality} />} />
        <SummaryMetric title="Poor" value={summary.data.poor_count} severity="poor" />
        <SummaryMetric title="Critical" value={summary.data.critical_count} severity="critical" />
        <SummaryMetric title="Insufficient data" value={summary.data.insufficient_data_count} />
        <SummaryMetric title="Latest measurement" value={dateTime(summary.data.latest_measurement?.measured_at)} compact />
      </section>
      <Distribution summary={summary.data} />
    </>}

    <NetworkQualityTrends filters={{ range: filters.range, campus: filters.campus, building: filters.building, location: filters.location, network: filters.network, device: filters.device }} />

    <AnalyticsTable title="Locations requiring attention" description="Locations with poor or critical measurements, in backend priority order." query={problemLocations} pageKey="problem-locations" pages={pages} setPages={setPages} empty="No locations currently require attention for the selected period." columns={[
      ['Location', (row) => <strong>{row.location_name}</strong>], ['Building', (row) => row.building_name ?? '—'], ['Overall quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count], ['Poor', (row) => row.poor_count], ['Critical', (row) => row.critical_count], ['Latest measurement', (row) => dateTime(row.latest_measurement?.measured_at)],
    ]} />
    <AnalyticsTable title="Devices with poor recent measurements" description="Quality classifications do not imply a hardware failure." query={problemDevices} pageKey="problem-devices" pages={pages} setPages={setPages} empty="No devices have poor or critical measurements for the selected period." columns={[
      ['Device', (row) => <><strong>{row.device_code}</strong><span className="table-subtitle">{row.device_name}</span></>], ['Type', (row) => label(row.device_type ?? 'Unknown')], ['Location', (row) => row.location_name ?? '—'], ['Overall quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count], ['Poor', (row) => row.poor_count], ['Critical', (row) => row.critical_count], ['Latest measurement', (row) => dateTime(row.latest_measurement?.measured_at)],
    ]} />
    <section className="quality-section-grid">
      <FactorTable query={factors} page={pages.factors ?? 1} setPage={(page) => setPages((current) => ({ ...current, factors: page }))} />
    <AnalyticsTable title="Network summary" description="Per-network measurements for the selected window." query={networks} pageKey="networks" pages={pages} setPages={setPages} empty="No network measurements found for this period." columns={[
        ['Network', (row) => <><strong>{row.network_name}</strong><span className="table-subtitle">{row.campus_name}</span></>], ['Type', (row) => label(row.network_type ?? 'Unknown')], ['Quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count], ['Poor / critical', (row) => `${row.poor_count} / ${row.critical_count}`],
      ]} />
    </section>
    <AnalyticsTable title="Device summary" description="Measurements for all represented devices; device state is inventory data, not a health check." query={devices} pageKey="devices" pages={pages} setPages={setPages} empty="No device measurements found for this period." columns={[
      ['Device', (row) => <><strong>{row.device_code}</strong><span className="table-subtitle">{row.device_name}</span></>], ['Type', (row) => label(row.device_type ?? 'Unknown')], ['Location', (row) => row.location_name ?? '—'], ['Quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count], ['Poor / critical', (row) => `${row.poor_count} / ${row.critical_count}`],
    ]} />
    <section className="quality-section-grid">
      <AnalyticsTable title="Campus summary" description="Campuses represented in the selected measurements." query={campuses} pageKey="campuses" pages={pages} setPages={setPages} empty="No campus measurements found for this period." columns={[
        ['Campus', (row) => row.campus_name], ['Quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count], ['Poor / critical', (row) => `${row.poor_count} / ${row.critical_count}`],
      ]} />
      <AnalyticsTable title="Building summary" description="Buildings represented in the selected measurements." query={buildings} pageKey="buildings" pages={pages} setPages={setPages} empty="No building measurements found for this period." columns={[
        ['Building', (row) => row.building_name], ['Campus', (row) => row.campus_name], ['Quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count],
      ]} />
    </section>
    <AnalyticsTable title="Location summary" description="All represented locations; the attention table above is limited to poor or critical locations." query={locations} pageKey="locations" pages={pages} setPages={setPages} empty="No location measurements found for this period." columns={[
      ['Location', (row) => row.location_name], ['Building', (row) => row.building_name ?? '—'], ['Quality', (row) => <QualityBadge quality={row.overall_quality} />], ['Measurements', (row) => row.measurement_count], ['Poor / critical', (row) => `${row.poor_count} / ${row.critical_count}`],
    ]} />
    <RecentMeasurements query={recent} page={pages.recent ?? 1} setPage={(page) => setPages((current) => ({ ...current, recent: page }))} filtersSupported={recentFiltersSupported} />
  </div>
}

function IdFilter({ title, value, onChange }: { title: string; value: string; onChange: (value: string) => void }) { return <label>{title}<input className="field" type="number" min="1" inputMode="numeric" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Any" /></label> }
function useGroupQuery(key: string, endpoint: string, filters: Filters, page: number) { return useQuery({ queryKey: ['network-quality', key, filters, page], queryFn: () => apiRequest<AnalyticsPage<AnalyticsGroup>>(queryPath(endpoint, filters, page)) }) }
function SummaryMetric({ title, value, severity, compact = false }: { title: string; value: ReactNode; severity?: 'poor' | 'critical'; compact?: boolean }) { return <article className={`quality-metric ${severity ? `quality-metric--${severity}` : ''}`}><span>{title}</span><strong className={compact ? 'quality-metric__compact' : ''}>{value}</strong></article> }
function QualityBadge({ quality }: { quality: string }) { return <Badge tone={qualityTone(quality)}>{label(quality)}</Badge> }

function Distribution({ summary }: { summary: NetworkAnalyticsSummary }) {
  return <section className="content-section quality-distribution"><div className="section-heading"><div><h2>Quality distribution</h2><p>Share of measurements by evaluator classification.</p></div></div><div className="distribution-body"><div className="distribution-bars" role="img" aria-label="Horizontal bars show quality distribution percentages; accessible values are listed in the table below.">{qualities.map((quality) => { const item = summary.quality_distribution[quality]; return <div className="distribution-row" key={quality}><span>{label(quality)}</span><div className="distribution-track"><div className={`distribution-fill distribution-fill--${quality.toLowerCase()}`} style={{ width: `${item.percentage}%` }} /></div><strong>{item.percentage.toFixed(2)}%</strong></div> })}</div><div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Quality</th><th scope="col">Measurements</th><th scope="col">Share</th></tr></thead><tbody>{qualities.map((quality) => <tr key={quality}><th scope="row"><QualityBadge quality={quality} /></th><td>{summary.quality_distribution[quality].count}</td><td>{summary.quality_distribution[quality].percentage.toFixed(2)}%</td></tr>)}</tbody></table></div></div></section>
}

type QueryPage<T> = { data?: AnalyticsPage<T>; isPending: boolean; isError: boolean; refetch: () => Promise<unknown> }
type Column = [string, (row: AnalyticsGroup) => ReactNode]
function AnalyticsTable({ title, description, query, pageKey, pages, setPages, empty, columns }: { title: string; description: string; query: QueryPage<AnalyticsGroup>; pageKey: string; pages: Record<string, number>; setPages: Dispatch<SetStateAction<Record<string, number>>>; empty: string; columns: Column[] }) {
  const data = query.data
  return <section className="content-section"><div className="section-heading"><div><h2>{title}</h2><p>{description}</p></div></div>{query.isPending ? <div className="quality-table-state"><Loading label={`Loading ${title.toLowerCase()}`} /></div> : query.isError ? <ErrorState title={`${title} could not be loaded`} detail="Retry this section or refresh the dashboard." onRetry={() => { void query.refetch() }} /> : !data || data.results.length === 0 ? <EmptyState title="No matching records" detail={empty} /> : <><div className="table-scroll"><table className="issue-table"><thead><tr>{columns.map(([heading]) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead><tbody>{data.results.map((row) => <tr key={row.id}>{columns.map(([heading, render]) => <td key={heading}>{render(row)}</td>)}</tr>)}</tbody></table></div><Pagination count={data.count} page={pages[pageKey] ?? 1} next={data.next} previous={data.previous} onPage={(page) => setPages((current) => ({ ...current, [pageKey]: page }))} /></>}</section>
}
function Pagination({ count, page, next, previous, onPage }: { count: number; page: number; next: string | null; previous: string | null; onPage: (page: number) => void }) { return <div className="pagination-bar"><span>{count} records · page {page}</span><div><Button disabled={!previous} onClick={() => onPage(page - 1)}>Previous</Button><Button disabled={!next} onClick={() => onPage(page + 1)}>Next</Button></div></div> }
function FactorTable({ query, page, setPage }: { query: QueryPage<AnalyticsFactor>; page: number; setPage: (page: number) => void }) {
  const data = query.data
  return <section className="content-section"><div className="section-heading"><div><h2>Primary degradation factors</h2><p>Share of degraded measurements · evaluator-selected factor, not confirmed root cause.</p></div></div>{query.isPending ? <div className="quality-table-state"><Loading label="Loading primary factors" /></div> : query.isError ? <ErrorState title="Primary factors could not be loaded" onRetry={() => { void query.refetch() }} /> : !data || data.results.length === 0 ? <EmptyState title="No degraded measurements" detail="No primary factors were reported for the selected period." /> : <><div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Factor</th><th scope="col">Count</th><th scope="col">Share of degraded</th></tr></thead><tbody>{data.results.map((factor) => <tr key={factor.factor}><td>{label(factor.factor)}</td><td>{factor.count}</td><td>{factor.percentage_of_degraded_measurements.toFixed(2)}%</td></tr>)}</tbody></table></div><Pagination count={data.count} page={page} next={data.next} previous={data.previous} onPage={setPage} /></>}</section>
}
function RecentMeasurements({ query, page, setPage, filtersSupported }: { query: { data?: { count: number; next: string | null; previous: string | null; results: NetworkMeasurementRecord[] }; isPending: boolean; isError: boolean; refetch: () => Promise<unknown> }; page: number; setPage: (page: number) => void; filtersSupported: boolean }) {
  const data = query.data
  return <section className="content-section"><div className="section-heading"><div><h2>Recent measurements</h2><p>Raw records use the analytics-returned time window and supported network, location, device, and connection filters.</p></div></div>{!filtersSupported ? <EmptyState title="Adjust filters to view raw measurements" detail="The raw-record API cannot apply the selected campus, building, device type, network type, or derived quality filter. Analytics summaries above still reflect those filters." /> : query.isPending ? <div className="quality-table-state"><Loading label="Loading recent measurements" /></div> : query.isError ? <ErrorState title="Recent measurements could not be loaded" detail="The analytics summary is available separately; retry the raw-record request." onRetry={() => { void query.refetch() }} /> : !data || data.results.length === 0 ? <EmptyState title="No recent measurements" detail="No raw measurement records match the selected period and supported raw-record filters." /> : <><div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Measured at</th><th scope="col">Network</th><th scope="col">Location</th><th scope="col">Device</th><th scope="col">Quality</th><th scope="col">Connection</th></tr></thead><tbody>{data.results.map((row) => <tr key={row.id}><td>{dateTime(row.measured_at)}</td><td>{row.network_name}</td><td>{row.location_name}</td><td>{row.device_code ?? 'Not linked'}</td><td><QualityBadge quality={row.quality_evaluation.overall_quality} /></td><td>{label(row.connection_state)}</td></tr>)}</tbody></table></div><Pagination count={data.count} page={page} next={data.next} previous={data.previous} onPage={setPage} /></>}</section>
}
