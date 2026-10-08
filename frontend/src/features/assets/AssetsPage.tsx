import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '../../lib/api'
import type { AssetOption, Paginated } from '../../types/api'
import { EmptyState, ErrorState, Loading } from '../../components/ui'

export default function AssetsPage() {
  const assets = useQuery({ queryKey: ['assets'], queryFn: () => apiRequest<Paginated<AssetOption>>('/assets/') })
  return <section className="content-section"><div className="section-heading"><div><h2>Campus assets</h2><p>Registered assets and their campus locations.</p></div></div>
    {assets.isPending ? <div className="state-panel"><Loading label="Loading assets" /></div>
      : assets.isError ? <ErrorState title="Assets could not be loaded" detail="Check your connection and try again." onRetry={() => { void assets.refetch() }} />
        : assets.data.count === 0 ? <div className="state-panel"><EmptyState title="No assets are registered" detail="Development assets can be added with the documented seed command." /></div>
          : <div className="table-scroll"><table className="issue-table"><thead><tr><th scope="col">Asset code</th><th scope="col">Name</th><th scope="col">Type</th><th scope="col">Location</th><th scope="col">QR</th></tr></thead><tbody>{assets.data.results.map((asset) => <tr key={asset.id}><td>{asset.asset_code}</td><td>{asset.name}</td><td>{asset.asset_type}</td><td>{asset.location_name}</td><td><a className="text-link" href={asset.qr_endpoint} target="_blank" rel="noreferrer">Open QR code</a></td></tr>)}</tbody></table></div>}
  </section>
}
