import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, EmptyState, ErrorState, Loading } from '../../components/ui'
import { ApiError, apiRequest } from '../../lib/api'
import type { NotificationRecord, Paginated } from '../../types/api'

const PAGE_SIZE = 20

function notificationError(error: unknown) {
  return error instanceof ApiError ? error.message : 'The notification service could not be reached. Try again shortly.'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export default function NotificationsPage() {
  const [page, setPage] = useState(1)
  const cache = useQueryClient()
  const query = useQuery({
    queryKey: ['notifications', page],
    queryFn: () => apiRequest<Paginated<NotificationRecord>>(`/notifications/?page=${page}`),
  })
  const markRead = useMutation({
    mutationFn: (id: number) => apiRequest<NotificationRecord>(`/notifications/${id}/read/`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ['notifications'] }) },
  })

  if (query.isPending) return <div className="state-panel"><Loading label="Loading notifications" /></div>
  if (query.isError) return <ErrorState title="Notifications could not be loaded" detail={notificationError(query.error)} onRetry={() => { void query.refetch() }} />

  const pageCount = Math.max(1, Math.ceil(query.data.count / PAGE_SIZE))
  return <section className="notification-page" aria-labelledby="notifications-title">
    <div className="section-heading"><div><h2 id="notifications-title">Notifications</h2><p>Internal updates about issues and operational work visible to your account.</p></div></div>
    {markRead.isError && <p className="form-error" role="alert">{notificationError(markRead.error)}</p>}
    {query.data.count === 0 ? <div className="state-panel"><EmptyState title="No notifications yet" detail="Updates relevant to your account will appear here." /></div> : <>
      <ol className="notification-list">
        {query.data.results.map((notification) => <li className={`notification-row ${notification.read_at ? 'notification-row--read' : 'notification-row--unread'}`} key={notification.id}>
          <div className="notification-copy"><div className="notification-meta"><Badge tone={notification.read_at ? 'neutral' : 'blue'}>{notification.read_at ? 'Read' : 'Unread'}</Badge><span>{notification.notification_type.replace(/_/g, ' ')}</span><time dateTime={notification.created_at}>{formatDate(notification.created_at)}</time></div><h3>{notification.title}</h3><p>{notification.message}</p>{notification.issue && <Link to={`/issues/${notification.issue}`}>Open linked issue</Link>}</div>
          {!notification.read_at && <Button type="button" disabled={markRead.isPending} onClick={() => markRead.mutate(notification.id)}>{markRead.isPending ? 'Saving…' : 'Mark as read'}</Button>}
        </li>)}
      </ol>
      {pageCount > 1 && <div className="pagination-bar"><span>{query.data.count} notifications · page {page} of {pageCount}</span><div><Button type="button" disabled={!query.data.previous || query.isFetching} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button><Button type="button" disabled={!query.data.next || query.isFetching} onClick={() => setPage((current) => current + 1)}>Next</Button></div></div>}
    </>}
  </section>
}
