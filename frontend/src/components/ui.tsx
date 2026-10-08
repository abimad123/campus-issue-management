import type { ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes, ReactNode } from 'react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' }
export function Button({ variant = 'secondary', className = '', ...props }: ButtonProps) {
  return <button className={`button button--${variant} ${className}`} {...props} />
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`field ${props.className ?? ''}`} {...props} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`field ${props.className ?? ''}`} {...props} />
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'red' | 'blue' | 'green' }) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <div className="state" role="status"><span className="spinner" aria-hidden="true" />{label}</div>
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><span className="empty-mark" aria-hidden="true">—</span><h3>{title}</h3><p>{detail}</p></div>
}

export function ErrorState({ title = 'Unable to load this view', detail = 'Try again in a moment.', onRetry }: { title?: string; detail?: string; onRetry?: () => void }) {
  return <div className="error-state" role="alert"><strong>{title}</strong><p>{detail}</p>{onRetry && <Button type="button" onClick={onRetry}>Try again</Button>}</div>
}
