import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { EmptyState, ErrorState, Loading } from '../../components/ui'
import { apiRequest } from '../../lib/api'
import type { NetworkTrendBucket, NetworkTrendResponse } from '../../types/api'

type TrendFilters = { range: '24h' | '7d' | '30d'; campus: string; building: string; location: string; network: string; device: string }
const series: { key: keyof NetworkTrendBucket; label: string; color: string }[] = [
  { key: 'excellent_percentage', label: 'Excellent', color: '#27805a' },
  { key: 'good_percentage', label: 'Good', color: '#78a184' },
  { key: 'fair_percentage', label: 'Fair', color: '#4d7896' },
  { key: 'poor_percentage', label: 'Poor', color: '#b87522' },
  { key: 'critical_percentage', label: 'Critical', color: '#a43b42' },
  { key: 'insufficient_data_percentage', label: 'Insufficient data', color: '#98a2b3' },
]

const displayLabel = (value: string) => value.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())
const bucketDate = (value: string, bucketSize: 'hour' | 'day') => new Intl.DateTimeFormat(undefined, bucketSize === 'hour' ? { month: 'short', day: 'numeric', hour: 'numeric' } : { month: 'short', day: 'numeric' }).format(new Date(value))

export default function NetworkQualityTrends({ filters }: { filters: TrendFilters }) {
  const path = useMemo(() => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value)
    return `/network-analytics/trends/?${params.toString()}`
  }, [filters])
  const query = useQuery({ queryKey: ['network-quality', 'trends', path], queryFn: () => apiRequest<NetworkTrendResponse>(path) })

  return <section className="content-section historical-trends" aria-labelledby="historical-trends-title">
    <div className="section-heading"><div><h2 id="historical-trends-title">Historical Trends</h2><p>Descriptive summaries of stored network measurements. This is not a forecast or live monitoring.</p></div></div>
    {query.isPending ? <div className="quality-table-state"><Loading label="Loading historical network quality trends" /></div> : query.isError ? <ErrorState title="Historical trend data could not be loaded." detail="The rest of the Network Quality dashboard remains available. Retry the trend request." onRetry={() => { void query.refetch() }} /> : query.data.buckets.length === 0 ? <EmptyState title="No historical measurements" detail="No network measurements were recorded during this period." /> : <>
      <TrendComparison response={query.data} />
      <TrendChart response={query.data} />
      <TrendTable response={query.data} />
      <FactorTrendTable response={query.data} />
    </>}
  </section>
}

function TrendComparison({ response }: { response: NetworkTrendResponse }) {
  const { comparison } = response
  const statusLabel = comparison.status === 'NO_COMPARISON' ? 'Not enough historical buckets to compare' : displayLabel(comparison.status)
  return <div className="trend-comparison" aria-label="Historical comparison">
    <div><span>Historical direction</span><strong>{statusLabel}</strong></div>
    {comparison.first_degraded_percentage !== null && comparison.latest_degraded_percentage !== null && comparison.change_percentage_points !== null ? <>
      <div><span>Degraded measurements</span><strong>{comparison.first_degraded_percentage.toFixed(2)}% → {comparison.latest_degraded_percentage.toFixed(2)}%</strong></div>
      <div><span>Change</span><strong>{comparison.change_percentage_points > 0 ? '+' : ''}{comparison.change_percentage_points.toFixed(2)} percentage points</strong></div>
    </> : <p>Two populated time buckets are needed for a descriptive comparison.</p>}
  </div>
}

function TrendChart({ response }: { response: NetworkTrendResponse }) {
  const { buckets, bucket_size: bucketSize } = response
  const width = Math.max(620, buckets.length * 38)
  const height = 250
  const plot = { left: 42, right: width - 12, top: 14, bottom: 198 }
  const plotHeight = plot.bottom - plot.top
  const step = (plot.right - plot.left) / buckets.length
  const barWidth = Math.max(5, Math.min(22, step * 0.66))
  const labelEvery = Math.max(1, Math.ceil(buckets.length / 8))

  return <div className="trend-chart-panel">
    <div className="trend-chart-heading"><h3>Quality distribution over time</h3><span>{bucketSize === 'hour' ? 'Hourly' : 'Daily'} buckets · populated periods only</span></div>
    <div className="trend-legend" aria-hidden="true">{series.map((item) => <span key={item.key}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}</div>
    <div className="trend-chart-scroll">
      <svg className="trend-chart-svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="trend-chart-title trend-chart-description">
        <title id="trend-chart-title">Historical network quality distribution</title>
        <desc id="trend-chart-description">100 percent stacked bars show the share of each evaluated quality classification for every populated {bucketSize} bucket. The accessible data table follows.</desc>
        {[0, 50, 100].map((percent) => {
          const y = plot.bottom - plotHeight * percent / 100
          return <g key={percent}><line x1={plot.left} x2={plot.right} y1={y} y2={y} stroke="#eaecf0" /><text x={plot.left - 7} y={y + 4} textAnchor="end" fill="#667085" fontSize="10">{percent}%</text></g>
        })}
        {buckets.map((bucket, index) => {
          const x = plot.left + step * index + (step - barWidth) / 2
          let offset = 0
          return <g key={bucket.bucket}>
            {series.map((item) => {
              const percentage = Number(bucket[item.key])
              const segmentHeight = plotHeight * percentage / 100
              const y = plot.bottom - offset - segmentHeight
              offset += segmentHeight
              return segmentHeight > 0 ? <rect key={item.key} x={x} y={y} width={barWidth} height={segmentHeight} fill={item.color}><title>{`${bucketDate(bucket.bucket, bucketSize)}: ${item.label} ${percentage.toFixed(2)}%`}</title></rect> : null
            })}
            {index % labelEvery === 0 && <text x={x + barWidth / 2} y={plot.bottom + 18} textAnchor="middle" fill="#667085" fontSize="10">{bucketDate(bucket.bucket, bucketSize)}</text>}
          </g>
        })}
      </svg>
    </div>
  </div>
}

function TrendTable({ response }: { response: NetworkTrendResponse }) {
  const { buckets, bucket_size: bucketSize } = response
  return <div className="trend-table-block"><h3>Historical values</h3><div className="table-scroll trend-table-scroll"><table className="issue-table"><thead><tr><th scope="col">Time bucket</th><th scope="col">Total</th><th scope="col">Excellent</th><th scope="col">Good</th><th scope="col">Fair</th><th scope="col">Poor</th><th scope="col">Critical</th><th scope="col">Insufficient data</th><th scope="col">Degraded</th><th scope="col">Poor / critical</th><th scope="col">Overall</th></tr></thead><tbody>{buckets.map((bucket) => <tr key={bucket.bucket}><th scope="row">{bucketDate(bucket.bucket, bucketSize)}</th><td>{bucket.total_measurements}</td><td>{bucket.excellent}</td><td>{bucket.good}</td><td>{bucket.fair}</td><td>{bucket.poor}</td><td>{bucket.critical}</td><td>{bucket.insufficient_data}</td><td>{bucket.degraded}</td><td>{bucket.poor_or_critical}</td><td>{displayLabel(bucket.overall_quality)}</td></tr>)}</tbody></table></div></div>
}

function FactorTrendTable({ response }: { response: NetworkTrendResponse }) {
  return <div className="trend-table-block"><h3>Primary evaluated factors</h3><p className="trend-table-note">These are evaluator-selected degradation factors, not confirmed physical root causes.</p><div className="table-scroll trend-table-scroll"><table className="issue-table"><thead><tr><th scope="col">Time bucket</th><th scope="col">Primary evaluated factors</th></tr></thead><tbody>{response.factor_trend.map((row) => <tr key={row.bucket}><th scope="row">{bucketDate(row.bucket, response.bucket_size)}</th><td>{row.factors.length ? row.factors.map((factor) => `${displayLabel(factor.factor)} (${factor.count})`).join(' · ') : 'No primary factors'}</td></tr>)}</tbody></table></div></div>
}
