import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import {
  Activity, ArrowDownRight, ArrowRight, BadgeCheck, Building2,
  Eye, EyeOff, LockKeyhole, Network, Radio, ShieldCheck, Signal, UserRound, Wifi,
} from 'lucide-react'
import { ApiError, apiRequest } from '../../lib/api'
import type { AuthUser } from '../../types/api'
import './LoginPage.css'

type HealthResponse = { status: string; service: string }

export default function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const reduceMotion = useReducedMotion()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const health = useQuery({
    queryKey: ['public-health'],
    queryFn: () => apiRequest<HealthResponse>('/health/'),
    retry: 1,
    staleTime: 30_000,
  })

  const login = useMutation({
    mutationFn: () => apiRequest<AuthUser>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ identifier, password }),
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
  const serviceOnline = health.data?.status === 'ok'
  const entrance = reduceMotion ? {} : { initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 } }

  return <main className="login-screen">
    <section className="login-showcase" aria-label="CampusOps platform overview">
      <div className="login-showcase-inner">
        <a className="login-brand" href="/" aria-label="CampusOps home">
          <span className="login-brand-mark"><Building2 size={19} aria-hidden="true" /></span>
          <span>CampusOps</span>
          <span className="login-brand-divider" />
          <span className={`login-health-dot ${serviceOnline ? 'is-online' : health.isPending ? 'is-pending' : 'is-offline'}`} />
          
        </a>

        <motion.div className="login-showcase-copy" {...entrance} transition={{ duration: 0.45 }}>
          <h1>Campus service work, with clear ownership.</h1>
          <p>Track issue lifecycles, coordinate verified technical work, and review operator-submitted network measurements across campus locations.</p>
        </motion.div>

        <motion.div className="login-metrics-panel" {...entrance} transition={{ duration: 0.5, delay: 0.08 }}>
          <div className="login-metrics-heading"><div><span className="login-panel-kicker">NETWORK &amp; OPERATIONS</span><h2>At a glance</h2></div><span className="login-sample-badge"><Activity size={12} /> Example values</span></div>
          <p className="login-sample-note">Illustrative snapshot · these are not live campus readings</p>
          <div className="login-metrics-grid">
            <div className="login-metric"><span><Wifi size={14} /> Wi-Fi latency</span><strong>24 <small>ms</small></strong><em>Sample reading</em></div>
            <div className="login-metric"><span><Network size={14} /> Packet loss</span><strong>0.2 <small>%</small></strong><em>Sample reading</em></div>
            <div className="login-metric login-metric-wide"><span><BadgeCheck size={14} /> SLA compliance</span><strong>98.4 <small>%</small></strong><em>Illustrative sample</em></div>
          </div>
          <div className="login-feature-pills"><span><ShieldCheck size={13} /> Four-role access</span><span><Activity size={13} /> SLA escalation</span><span><Signal size={13} /> Reviewed network context</span></div>
        </motion.div>

        <div className="login-showcase-footer"><span><LockKeyhole size={13} /> Role permissions are checked by the backend</span><a href="/">About the project <ArrowDownRight size={13} /></a></div>
      </div>
    </section>

    <section className="login-form-side" aria-labelledby="login-title">
      <motion.div className="login-card" {...entrance} transition={{ duration: 0.45, delay: 0.05 }}>
        <div className="login-form-heading">
          <span className="login-form-icon"><UserRound size={18} aria-hidden="true" /></span>
          <p className="login-eyebrow">PROJECT WORKSPACE</p>
          <h2 id="login-title">Sign in to Workspace</h2>
          <p>Sign in using your campus ID or registered email and account password. Your account access is identified automatically.</p>
        </div>

        {message && <div className="login-error" role="alert">{message}</div>}

        <form className="login-form" onSubmit={submit}>
          <div className="login-field">
            <label htmlFor="login-identifier">Student ID, Employee ID, or Email</label>
            <div className="login-input-wrap"><UserRound size={17} aria-hidden="true" /><input id="login-identifier" name="identifier" autoComplete="username" autoCapitalize="none" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required placeholder="Enter your ID or email" /></div>
          </div>
          <div className="login-field">
            <div className="login-label-row"><label htmlFor="login-password">Password</label><span>Keep your password private</span></div>
            <div className="login-input-wrap"><LockKeyhole size={17} aria-hidden="true" /><input id="login-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required placeholder="Enter your password" /><button className="login-password-toggle" type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
          </div>
          <div className="login-form-options"><span><ShieldCheck size={14} /> Secure sign-in</span><span>Password help? Contact your project Admin.</span></div>
          <button className="login-submit" type="submit" disabled={login.isPending}>{login.isPending ? 'Signing in…' : 'Sign In to Dashboard'}<ArrowRight size={17} aria-hidden="true" /></button>
        </form>

        <div className="login-security-note"><LockKeyhole size={14} aria-hidden="true" /><p>Protected by role-based access control. Academic project workspace for campus operations management.</p></div>
      </motion.div>
      <p className="login-project-note">CampusOps is an academic project and is not an official LPU service.</p>
    </section>
  </main>
}
