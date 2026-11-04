import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import {
  Activity, ArrowRight, ArrowUpRight, BadgeCheck,
  Check, ClipboardCheck, Clock3, FileText, GraduationCap, HardDrive, KeyRound,
  Building2, Layers3, LockKeyhole, MapPin, Network, Radio, Server, Settings2,
  ShieldCheck, Signal, UserRound, Wifi, Wrench, Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { apiRequest } from '../../lib/api'
import { useQuery } from '@tanstack/react-query'
import './LandingPage.css'

type HealthResponse = { status: string; service: string }

const lifecycleStages = [
  { label: 'Open', icon: FileText },
  { label: 'Assigned', icon: ArrowUpRight },
  { label: 'In progress', icon: Wrench },
  { label: 'Resolved', icon: Check },
]

const moduleTabs = [
  {
    id: 'intake', label: 'Issue intake', title: 'A clear report, with its full context.',
    copy: 'Students and staff submit a category, campus location and description. Staff can request high queue priority with a reason; routing and SLA selection remain based on the captured routing priority.',
    points: ['Structured location and category', 'Staff priority requests include a reason', 'Reporter-scoped issue history'],
    icon: FileText,
  },
  {
    id: 'routing', label: 'Routing & assignment', title: 'Rules route work to an eligible team member.',
    copy: 'Admins configure rules by category, location and routing priority. Matching issues go to the eligible technical staff member with the lowest active workload; outcomes and assignment history are retained.',
    points: ['Configurable category, location and priority rules', 'Least-workload technical assignment', 'Unassigned work stays in the Admin queue'],
    icon: Network,
  },
  {
    id: 'sla', label: 'SLA & escalation', title: 'Deadlines remain attached to the issue.',
    copy: 'A periodic background sweep records warnings, breaches and escalations. Persisted timestamps keep the lifecycle intact across restarts.',
    points: ['Stored response and resolution deadlines', 'Idempotent breach and warning events', 'Role-based internal notifications'],
    icon: Clock3,
  },
  {
    id: 'work-orders', label: 'Work orders', title: 'Field work has its own verified lifecycle.',
    copy: 'Assigned technical staff accept work, log effort and materials, and submit private evidence. An Admin verifies completion or requests rework before the issue is resolved.',
    points: ['Assigned technical staff execute field work', 'Notes, materials and private proof', 'Admin verification and rework'],
    icon: Wrench,
  },
]

const roles: Array<{ title: string; responsibility: string; scope: string; icon: LucideIcon }> = [
  { title: 'Student', responsibility: 'Report campus issues', scope: 'Own reports', icon: GraduationCap },
  { title: 'Staff', responsibility: 'Report campus issues', scope: 'Own reports', icon: UserRound },
  { title: 'Technical Staff', responsibility: 'Execute assigned work', scope: 'Team-specialized assignments', icon: Wrench },
  { title: 'Admin', responsibility: 'Coordinate campus operations', scope: 'Issues, routing, SLA, work & network', icon: ShieldCheck },
]

const stack = [
  { label: 'Frontend', value: 'React · TypeScript · Tailwind CSS', icon: Layers3 },
  { label: 'Backend engine', value: 'Django REST Framework · PostgreSQL', icon: Server },
  { label: 'Background jobs', value: 'Celery · Redis', icon: Zap },
  { label: 'Infrastructure', value: 'Docker Compose', icon: HardDrive },
]

const faqItems = [
  {
    question: 'Who can use the platform?',
    answer: 'The current account roles are Student, Staff, Technical Staff, and Admin. Access to issues and operational actions is checked by the backend for each role.',
  },
  {
    question: 'How are new issues assigned?',
    answer: 'Admins configure routing rules using issue category, location, and routing priority. A matching issue is assigned to an eligible Technical Staff member with the lowest active workload. If nobody is eligible, it stays in the Admin queue.',
  },
  {
    question: 'Can staff mark an issue as high priority?',
    answer: 'Staff can request high queue priority and must give a reason. The request affects queue ordering; it does not change the routing priority or the SLA deadlines already selected for the issue.',
  },
  {
    question: 'How do SLAs and escalations work?',
    answer: 'Response and resolution deadlines are stored on the issue. A periodic background process records warnings, breaches, and escalation events. Reopening an issue retains its original SLA deadlines and history.',
  },
  {
    question: 'Does the platform monitor campus Wi-Fi devices live?',
    answer: 'No. Network measurements are submitted by an operator and evaluated with deterministic rules. The project does not poll access points or routers or connect to external monitoring systems.',
  },
  {
    question: 'Are the campus examples real?',
    answer: 'No. The page uses illustrative, synthetic examples for an academic project set in an LPU campus context. This is not an official LPU service or affiliation.',
  },
]

function formatCountdown(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${hours}h ${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`
}

function SectionEyebrow({ children }: { children: string }) {
  return <p className="landing-eyebrow">{children}</p>
}

export default function LandingPage() {
  const reduceMotion = useReducedMotion()
  const [activeTab, setActiveTab] = useState(moduleTabs[0].id)
  const [sampleSeconds, setSampleSeconds] = useState(3 * 60 * 60 + 14 * 60)
  const health = useQuery({
    queryKey: ['public-health'],
    queryFn: () => apiRequest<HealthResponse>('/health/'),
    retry: 1,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
  const selectedModule = moduleTabs.find((tab) => tab.id === activeTab) ?? moduleTabs[0]

  useEffect(() => {
    const interval = window.setInterval(() => setSampleSeconds((seconds) => Math.max(0, seconds - 1)), 1000)
    return () => window.clearInterval(interval)
  }, [])

  const entrance = reduceMotion ? {} : { initial: { opacity: 0, y: 18 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, amount: 0.15 } }
  const serviceOnline = health.data?.status === 'ok'
  const serviceLabel = health.isPending ? 'Checking API' : serviceOnline ? 'API responding' : 'API unavailable'

  return <div className="landing-page">
    <header className="landing-header">
      <div className="landing-header-inner">
        <Link to="/" className="landing-brand" aria-label="CampusOps home">
          <span className={`landing-brand-dot ${serviceOnline ? 'is-online' : ''}`} aria-hidden="true" />
          <span>CampusOps</span>
          <span className="landing-brand-context">LPU project</span>
        </Link>
        <nav className="landing-nav" aria-label="Landing page sections">
          <a href="#issues">Issue Tracker</a>
          <a href="#network-quality">Network Quality</a>
          <a href="#issues" onClick={() => setActiveTab('sla')}>SLA Rules</a>
          <a href="#issues" onClick={() => setActiveTab('work-orders')}>Work Orders</a>
          <a href="#roles">Role Matrix</a>
          <a href="#faq">FAQ</a>
        </nav>
        <div className="landing-header-actions">
          <a className="landing-button landing-button-ghost" href="#roles">Role Selection Matrix</a>
          <Link className="landing-button landing-button-dark" to="/login">Access Portal <ArrowUpRight size={15} aria-hidden="true" /></Link>
        </div>
      </div>
    </header>

    <main>
      <section className="landing-hero landing-wrap">
        <motion.div className="landing-hero-copy" {...entrance} transition={{ duration: 0.55, ease: 'easeOut' }}>
          <div className="landing-version-badge"><Radio size={14} aria-hidden="true" /> Operator-assisted network findings <span>Current scope</span></div>
          <h1>Campus Issue Management &amp; Network Quality Analysis</h1>
          <p className="landing-hero-lede">A shared workspace for campus issue intake, rule-based assignment, persistent SLA tracking, verified technical work, and operator-submitted network measurements.</p>
          <p className="landing-hero-note">Measurements are operator-submitted and evaluated with deterministic rules. The platform does not poll campus routers or access points.</p>
          <div className="landing-hero-actions">
            <Link className="landing-button landing-button-dark landing-button-large" to="/login">Launch Issue Portal <ArrowRight size={17} aria-hidden="true" /></Link>
            <a className="landing-button landing-button-outline landing-button-large" href="#network-quality">Explore Network Quality <Signal size={16} aria-hidden="true" /></a>
          </div>
          <div className="landing-hero-proof"><span><Check size={14} /> Role-scoped access</span><span><Check size={14} /> Auditable workflows</span><span><Check size={14} /> PostgreSQL-backed</span></div>
        </motion.div>

        <motion.div className="preview-shell" {...entrance} transition={{ duration: 0.65, delay: 0.12, ease: 'easeOut' }} aria-label="Illustrative campus operations dashboard preview">
          <div className="preview-topbar"><div><span className="preview-window-dot" /><span className="preview-window-dot" /><span className="preview-window-dot" /></div><span className="preview-workspace">CAMPUS OPERATIONS · SAMPLE VIEW</span><span className="preview-tag"><Activity size={13} /> Illustrative</span></div>
          <div className="preview-notice"><span className="preview-notice-dot" /> Synthetic example data · not live network telemetry</div>
          <div className="preview-content">
            <article className="preview-issue">
              <div className="preview-card-heading"><span className="preview-icon"><Wifi size={16} /></span><span className="preview-kicker">CAMPUS ISSUE</span><span className="preview-status">In progress</span></div>
              <p className="preview-ticket">ISS-2026-000184</p>
              <h2>LPU Classroom 302</h2>
              <p className="preview-issue-summary">Wi-Fi access point reporting packet loss above 12%</p>
              <div className="preview-location"><MapPin size={13} /> Academic Block · Room 302</div>
              <div className="preview-sla"><div><span className="preview-sla-label"><Clock3 size={13} /> Resolution SLA</span><span className="preview-countdown">{formatCountdown(sampleSeconds)}</span></div><span className="preview-sla-track"><i /></span><small>Illustrative countdown · sample ticket</small></div>
              <div className="preview-assignment"><span className="preview-avatar">NO</span><span><strong>Network Operations</strong><small>Assigned team</small></span><ArrowUpRight size={15} /></div>
            </article>
            <article className="preview-network">
              <div className="preview-network-header"><div><span className="preview-kicker">NETWORK QUALITY</span><h2>Rule evaluation</h2></div><span className="preview-quality"><BadgeCheck size={14} /> EXCELLENT</span></div>
              <div className="quality-summary"><div className="quality-score-ring"><BadgeCheck size={25} aria-hidden="true" /></div><div className="quality-caption"><strong>EXCELLENT</strong><span>Overall quality · example reading</span></div></div>
              <div className="preview-metrics">
                <div><span><Activity size={13} /> Latency</span><strong>24 <small>ms</small></strong><em>Excellent</em></div>
                <div><span><Network size={13} /> Packet loss</span><strong>0.4 <small>%</small></strong><em>Excellent</em></div>
                <div><span><Signal size={13} /> Signal</span><strong>-62 <small>dBm</small></strong><em>Good</em></div>
              </div>
              <div className="preview-disclaimer"><LockKeyhole size={13} /> Sample values only; no device polling is configured.</div>
            </article>
          </div>
          <div className="preview-foot"><span><span className={`landing-status-dot ${serviceOnline ? 'is-online' : health.isPending ? 'is-pending' : 'is-offline'}`} />{serviceLabel}</span><span>Example evaluation · v1.0</span></div>
        </motion.div>
      </section>

      <section id="issues" className="landing-section landing-wrap">
        <motion.div className="landing-section-heading" {...entrance} transition={{ duration: 0.5 }}>
          <div><SectionEyebrow>ONE OPERATIONAL WORKFLOW</SectionEyebrow><h2>From first report to verified resolution.</h2></div>
          <p>Issue management and network quality work together while keeping their records, permissions and responsibilities clear.</p>
        </motion.div>
        <div className="pillars-grid">
          <article className="pillar-card issue-pillar">
            <div className="pillar-topline"><span className="pillar-icon"><ClipboardCheck size={18} /></span><span className="pillar-index">01 / ISSUE LIFECYCLE</span></div>
            <h3>Campus Issue &amp; SLA Lifecycle Management</h3>
            <p>Student and staff reports connect configurable routing, durable SLA tracking, and technical staff work orders with Admin verification.</p>
            <div className="module-tabs" role="group" aria-label="Issue lifecycle details">
              {moduleTabs.map((tab) => <button key={tab.id} type="button" className={activeTab === tab.id ? 'is-active' : ''} aria-pressed={activeTab === tab.id} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
            </div>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div className="module-tab-content" key={selectedModule.id} initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? undefined : { opacity: 0, y: -6 }} transition={{ duration: 0.2 }}>
                <div className="tab-title-row"><span><selectedModule.icon size={17} /></span><h4>{selectedModule.title}</h4></div>
                <p>{selectedModule.copy}</p>
                <ul>{selectedModule.points.map((point) => <li key={point}><Check size={14} />{point}</li>)}</ul>
              </motion.div>
            </AnimatePresence>
            <div className="lifecycle" aria-label="Issue status flow">
              {lifecycleStages.map((stage, index) => <div className="lifecycle-stage" key={stage.label}><span className={index < 2 ? 'stage-marker stage-marker-done' : 'stage-marker'}><stage.icon size={13} /></span><span>{stage.label}</span>{index < lifecycleStages.length - 1 && <i aria-hidden="true" />}</div>)}
            </div>
            <p className="lifecycle-note">Issue states are separate from work-order states; administrator verification records resolution.</p>
          </article>

          <article id="network-quality" className="pillar-card network-pillar">
            <div className="pillar-topline"><span className="pillar-icon"><Signal size={18} /></span><span className="pillar-index">02 / NETWORK FOUNDATION</span></div>
            <h3>Deterministic Network Quality Analysis</h3>
            <p>Store operator-submitted readings, evaluate them with explicit rules and attach reviewed findings to an issue.</p>
            <div className="network-capabilities">
              <div><span className="capability-icon"><Activity size={15} /></span><span><strong>Raw metric storage</strong><small>Latency · loss · download · upload · signal</small></span></div>
              <div><span className="capability-icon"><Settings2 size={15} /></span><span><strong>Predefined rule evaluator</strong><small>Deterministic thresholds · no ML</small></span></div>
              <div><span className="capability-icon"><ArrowRight size={15} /></span><span><strong>Finding to issue context</strong><small>Operator reviewed · provenance retained</small></span></div>
            </div>
            <div className="evaluation-preview">
              <div className="evaluation-title"><span>ILLUSTRATIVE RULE TABLE</span><span>Evaluator v1.0</span></div>
              <div className="evaluation-row evaluation-head"><span>Metric / rule</span><span>Reading</span><span>Outcome</span></div>
              <div className="evaluation-row"><span><i className="metric-dot metric-dot-green" /> LATENCY</span><strong>24 ms</strong><em className="outcome-good">EXCELLENT</em></div>
              <div className="evaluation-row"><span><i className="metric-dot metric-dot-amber" /> LATENCY</span><strong>185 ms</strong><em className="outcome-warn">POOR</em></div>
              <div className="evaluation-row"><span><i className="metric-dot metric-dot-green" /> PACKET_LOSS</span><strong>0.4%</strong><em className="outcome-good">EXCELLENT</em></div>
            </div>
            <div className="network-footnote"><Radio size={14} /> Measurements are not live router or access-point telemetry.</div>
          </article>
        </div>
      </section>

      <section id="roles" className="landing-section landing-roles-section">
        <div className="landing-wrap">
          <motion.div className="landing-section-heading" {...entrance} transition={{ duration: 0.5 }}>
            <div><SectionEyebrow>THE CURRENT ACCESS MODEL</SectionEyebrow><h2>Student, Staff, Technical Staff, and Admin.</h2></div>
            <p>These are the four account roles in the current project. Technical specializations are profile data, and permissions are enforced by the backend.</p>
          </motion.div>
          <div className="role-grid">
            {roles.map((role, index) => <motion.article className="role-card" key={role.title} {...entrance} transition={{ duration: 0.35, delay: reduceMotion ? 0 : index * 0.035 }}>
              <div className="role-card-head"><span className="role-icon"><role.icon size={17} /></span><span className="role-order">0{index + 1}</span></div>
              <h3>{role.title}</h3>
              <span className="role-responsibility">{role.responsibility}</span>
              <p><KeyRound size={13} />{role.scope}</p>
            </motion.article>)}
          </div>
        </div>
      </section>

      <section id="architecture" className="landing-section landing-wrap">
        <motion.div className="stack-heading" {...entrance} transition={{ duration: 0.5 }}>
          <div><SectionEyebrow>BUILT FOR MAINTAINABLE OPERATIONS</SectionEyebrow><h2>A familiar, serviceable foundation.</h2></div>
          <p>Relational data, background processing and containerized development keep operational workflows testable and clear.</p>
        </motion.div>
        <div className="stack-grid">
          {stack.map((item) => <div className="stack-item" key={item.label}><span className="stack-icon"><item.icon size={17} /></span><div><span>{item.label}</span><strong>{item.value}</strong></div><ArrowUpRight className="stack-arrow" size={15} /></div>)}
        </div>
      </section>

      <section id="faq" className="landing-section landing-faq-section">
        <div className="landing-wrap">
          <motion.div className="landing-section-heading" {...entrance} transition={{ duration: 0.5 }}>
            <div><SectionEyebrow>COMMON QUESTIONS</SectionEyebrow><h2>Clear answers about how the platform works.</h2></div>
            <p>Learn what the current project supports, how access is scoped, and where network measurements come from.</p>
          </motion.div>
          <div className="landing-faq-list">
            {faqItems.map((item, index) => <motion.details className="landing-faq-item" key={item.question} {...entrance} transition={{ duration: 0.3, delay: reduceMotion ? 0 : index * 0.025 }}>
              <summary>{item.question}<span aria-hidden="true">+</span></summary>
              <p>{item.answer}</p>
            </motion.details>)}
          </div>
        </div>
      </section>

      <section className="landing-cta-band landing-wrap">
        <div><span className="cta-symbol"><Building2 size={20} /></span><div><p>LOVELY PROFESSIONAL UNIVERSITY · ACADEMIC PROJECT CONTEXT</p><h2>One accountable place for campus service work.</h2><span>This project is not an official LPU service or affiliation.</span></div></div>
        <Link className="landing-button landing-button-dark landing-button-large" to="/login">Enter the project workspace <ArrowRight size={16} /></Link>
      </section>
    </main>

    <footer className="landing-footer">
      <div className="landing-wrap footer-inner"><Link to="/" className="landing-brand"><span className={`landing-brand-dot ${serviceOnline ? 'is-online' : ''}`} />CampusOps</Link><span className="footer-status"><span className={`landing-status-dot ${serviceOnline ? 'is-online' : health.isPending ? 'is-pending' : 'is-offline'}`} />{serviceLabel}<small> · liveness check</small></span><span>© {new Date().getFullYear()} Campus Operations · Academic project</span><div><a href="#issues">Workflows</a><a href="#roles">Role matrix</a><a href="#faq">FAQ</a><Link to="/login">Access portal</Link></div></div>
    </footer>
  </div>
}

