import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ApiError, apiRequest } from '../../lib/api'
import type { AuthUser } from '../../types/api'
import { Button, ErrorState, Input } from '../../components/ui'

export default function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: () => apiRequest<AuthUser>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
    onSuccess: (user) => {
      queryClient.setQueryData(['current-user'], user)
      navigate('/dashboard', { replace: true })
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    login.mutate()
  }

  const message = login.error instanceof ApiError
    ? login.error.message
    : login.error ? 'The service could not be reached. Try again shortly.' : null

  return <main className="auth-screen">
    <section className="auth-panel" aria-labelledby="login-title">
      <div className="brand auth-brand"><div className="brand-mark" aria-hidden="true">C</div><div><strong>Campus Operations</strong><span>Service platform</span></div></div>
      <p className="eyebrow">PROJECT WORKSPACE</p>
      <h1 id="login-title">Sign in</h1>
      <p className="auth-intro">Use your project account to view campus service requests.</p>
      {message && <div className="form-error" role="alert">{message}</div>}
      <form className="stacked-form" onSubmit={submit}>
        <label htmlFor="login-email">Email address</label>
        <Input id="login-email" name="email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label htmlFor="login-password">Password</label>
        <Input id="login-password" name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        <Button variant="primary" type="submit" disabled={login.isPending}>{login.isPending ? 'Signing in…' : 'Sign in'}</Button>
      </form>
      <p className="auth-footnote">Development accounts are created with the documented seed command. This project workspace is not an official LPU service.</p>
    </section>
  </main>
}
