import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  alternatives,
  initialPreferences,
  rawCalls,
  toolEvents,
  trip,
  type Alternative,
  type DemoStage,
  type ToolEvent,
  type ToolTier,
} from './data'
import { mcp } from './services/mcpClient'
import './styles.css'

/** Map polished UI alternative ids → backend mock flight ids */
const FLIGHT_MAP: Record<string, string> = {
  sas: 'FLIGHT-A',
  lufthansa: 'FLIGHT-B',
  finnair: 'FLIGHT-C',
}

type IconName =
  | 'arrow'
  | 'plane'
  | 'hotel'
  | 'car'
  | 'message'
  | 'shield'
  | 'pulse'
  | 'chevron'
  | 'close'
  | 'sliders'
  | 'clock'
  | 'check'
  | 'database'
  | 'spark'
  | 'refresh'
  | 'route'
  | 'user'
  | 'audit'
  | 'lock'
  | 'terminal'

const iconPaths: Record<IconName, string> = {
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  plane: 'M3 12h18M13 4l3 8-3 8M8 7l5 5-5 5',
  hotel: 'M4 18V7m0 7h16v4M4 11h6a3 3 0 0 1 3 3M20 18v-4',
  car: 'M5 17h14l-1.3-6.2A2.3 2.3 0 0 0 15.5 9h-7a2.3 2.3 0 0 0-2.2 1.8L5 17Zm0 0v2m14-2v2M8 17v.01M16 17v.01',
  message: 'M5 5h14v10H8l-3 3V5Zm4 5h6m-6-3h4',
  shield: 'M12 3 19 6v5c0 4.7-2.8 8-7 10-4.2-2-7-5.3-7-10V6l7-3Zm-3 9 2 2 4-4',
  pulse: 'M3 12h4l2-5 4 10 2-5h6',
  chevron: 'm9 18 6-6-6-6',
  close: 'm6 6 12 12M18 6 6 18',
  sliders: 'M4 6h16M4 12h16M4 18h16M8 4v4m8 2v4m-4 4v4',
  clock: 'M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  check: 'm5 12 4 4L19 6',
  database: 'M5 6c0-1.1 3.1-2 7-2s7 .9 7 2-3.1 2-7 2-7-.9-7-2Zm0 0v6c0 1.1 3.1 2 7 2s7-.9 7-2V6m-14 6v6c0 1.1 3.1 2 7 2s7-.9 7-2v-6',
  spark: 'm12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Zm7 13 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6L19 16Z',
  refresh: 'M20 11a8 8 0 0 0-14.7-4L4 9m0 0V4m0 5h5m-5 2a8 8 0 0 0 14.7 4L20 15m0 0v5m0-5h-5',
  route: 'M4 18c3 0 3-12 8-12s5 12 8 12M4 18h4m8 0h4',
  user: 'M20 21a8 8 0 0 0-16 0m12-12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  audit: 'M7 3h10v18H7zM10 7h4m-4 4h4m-4 4h2',
  lock: 'M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3',
  terminal: 'm5 7 4 5-4 5m7 0h7',
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={iconPaths[name]} />
    </svg>
  )
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-mark${compact ? ' brand-mark--compact' : ''}`}>
      <span className="brand-glyph" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none">
          <path d="M4 23c6.8 0 5.7-14 12-14 6.2 0 5.2 14 12 14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          <path d="M5 23h6m10 0h6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          <circle cx="16" cy="9" r="2" fill="currentColor" />
        </svg>
      </span>
      {!compact && (
        <span className="brand-type">
          <strong>TRIP</strong>
          <span>/ RESCUE</span>
          <small>AI SYSTEM</small>
        </span>
      )}
    </div>
  )
}

function StatusChip({ children, tone = 'neutral', dot = false }: { children: ReactNode; tone?: 'neutral' | 'amber' | 'teal' | 'blue' | 'coral'; dot?: boolean }) {
  return <span className={`status-chip status-chip--${tone}`}>{dot && <span className="chip-dot" />}{children}</span>
}

function TierBadge({ tier }: { tier: ToolTier }) {
  return <span className={`tier-badge tier-badge--${tier}`}>{tier}</span>
}

function AlternativeCard({ option, selected, onSelect }: { option: Alternative; selected: boolean; onSelect: () => void }) {
  return (
    <button className={`alternative-card${selected ? ' alternative-card--selected' : ''}`} onClick={onSelect} aria-pressed={selected}>
      <span className="option-accent" style={{ background: option.accent }} />
      <span className="alternative-topline">
        <span className="airline-lockup"><span className="airline-code">{option.code}</span><span><strong>{option.airline}</strong><small>{option.flight}</small></span></span>
        <span className="selection-indicator">{selected ? <Icon name="check" size={13} /> : null}</span>
      </span>
      <span className="alternative-route">{option.route}</span>
      <span className="alternative-times"><strong>{option.departure}</strong><span className="mini-route"><i /> <i /> <i /></span><strong>{option.arrival}</strong></span>
      <span className="alternative-meta"><span>{option.duration}</span><span>{option.stops}</span><span>{option.seat}</span></span>
      <span className="alternative-bottom"><span className="fit-copy"><Icon name="spark" size={14} />{option.fit}</span><strong className={option.delta > 75 ? 'price-over' : ''}>{option.delta > 0 ? '+' : option.delta < 0 ? '-' : ''}${Math.abs(option.delta)}</strong></span>
      <span className="tag-row">{option.tags.map((tag) => <span className="mini-tag" key={tag}>{tag}</span>)}</span>
    </button>
  )
}

const emptyPreferences = {
  airline: 'No saved airline',
  seat: 'Any seat',
  maxDelta: 'No limit',
  overnight: 'No saved rule',
  notifications: 'Draft messages, never send without approval',
}

function App() {
  const [stage, setStage] = useState<DemoStage>('review')
  const [selectedId, setSelectedId] = useState('sas')
  const [preferences, setPreferences] = useState(initialPreferences)
  const [preferencesDeleted, setPreferencesDeleted] = useState(false)
  const [preferencesOpen, setPreferencesOpen] = useState(false)
  const [rawCallsOpen, setRawCallsOpen] = useState(false)
  const [toast, setToast] = useState('')
  const [backendPlan, setBackendPlan] = useState<any>(null)
  const [backendResult, setBackendResult] = useState<any>(null)
  const [notificationDraft, setNotificationDraft] = useState<any>(null)
  const [notificationSent, setNotificationSent] = useState(false)
  const [sendingNotif, setSendingNotif] = useState(false)
  const [toolLog, setToolLog] = useState<string[]>([])
  const [backendError, setBackendError] = useState<string | null>(null)
  const [prefsLoading, setPrefsLoading] = useState(false)

  // Sync preferences from server on mount
  useEffect(() => {
    let active = true
    const loadServerPreferences = async () => {
      try {
        const res = await mcp.getPreferences()
        if (!active || !res) return
        setPreferences((prev) => {
          const updated = { ...prev }
          if (res.preferred_airline?.value) {
            updated.airline = res.preferred_airline.value === 'Example Air' ? 'SAS / Star Alliance' : String(res.preferred_airline.value)
          }
          if (res.seat?.value) {
            updated.seat = String(res.seat.value).toLowerCase() === 'window' ? 'Window' : 'Aisle'
          }
          if (res.max_additional_cost?.value !== undefined) {
            const v = Number(res.max_additional_cost.value)
            updated.maxDelta = v <= 75 ? '$75' : v <= 150 ? '$150' : 'No limit'
          }
          if (res.avoid_overnight?.value !== undefined) {
            updated.overnight = res.avoid_overnight.value ? 'Avoid overnight flights' : 'Overnight is okay'
          }
          return updated
        })
      } catch {
        // Backend offline or error; defaults remain
      }
    }
    loadServerPreferences()
    return () => { active = false }
  }, [])

  const rankedAlternatives = useMemo(() => {
    const score = (option: Alternative) => {
      let value = 0
      if (preferences.airline.includes('SAS') && option.airline === 'SAS') value += 4
      if (preferences.seat === 'Window' && option.seat.includes('window')) value += 2
      if (preferences.seat === 'Aisle' && option.seat.includes('aisle')) value += 2
      if (preferences.maxDelta === '$75' && option.delta <= 75) value += 2
      if (preferences.maxDelta === '$150') value += 1
      if (preferences.overnight === 'Avoid overnight flights' && option.arrival !== '12:10') value += 1
      return value
    }
    return [...alternatives].sort((a, b) => score(b) - score(a))
  }, [preferences])
  const selected = useMemo(() => alternatives.find((option) => option.id === selectedId) ?? alternatives[0], [selectedId])
  const isBusy = stage === 'executing'

  useEffect(() => {
    if (!preferencesOpen) return undefined
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPreferencesOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [preferencesOpen])

  const announce = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 3600)
  }

  const selectAlternative = (option: Alternative) => {
    if (isBusy) return
    setSelectedId(option.id)
    if (stage !== 'review') setStage('review')
    announce(`${option.airline} ${option.flight} is now the active rescue option.`)
  }

  const executePlan = async (outcome: 'recovered' | 'partial_failure' = 'recovered') => {
    if (isBusy) return
    setStage('executing')
    setBackendError(null)
    setBackendResult(null)
    setBackendPlan(null)
    setNotificationDraft(null)
    setNotificationSent(false)
    const log: string[] = []
    const pushLog = (line: string) => { log.push(line); setToolLog([...log]) }
    announce('Calling rescue server · propose → approve → execute…')
    const flightId = FLIGHT_MAP[selectedId] || 'FLIGHT-A'
    const forceFail = outcome === 'partial_failure' ? 'reschedule_ride' : undefined
    try {
      pushLog(`propose_rescue_plan({ selected_flight_id: "${flightId}" })`)
      const plan = await mcp.proposeRescuePlan(flightId)
      if (plan.error || !plan.plan_id) throw new Error(plan.error || 'Plan proposal failed')
      setBackendPlan(plan)
      pushLog(`// plan_id=${plan.plan_id} hash=${String(plan.plan_hash).slice(0, 16)}… cost=+${plan.total_cost_delta}`)

      pushLog(`approve_rescue_plan({ plan_id: "${plan.plan_id}", plan_hash: "…" })`)
      const approval = await mcp.approveRescuePlan(plan.plan_id, plan.plan_hash)
      if (!approval.ok) throw new Error(approval.message || approval.error || 'Approval failed')
      pushLog(`// approved expires=${approval.expires_at || 'n/a'}`)

      pushLog(`execute_rescue_plan({ plan_id: "${plan.plan_id}"${forceFail ? `, force_fail_step: "${forceFail}"` : ''} })`)
      const result = await mcp.executeRescuePlan(plan.plan_id, forceFail)
      setBackendResult(result)
      if (result.status === 'succeeded') {
        setStage('recovered')
        announce(`Backend confirmed success · plan ${plan.plan_id} · +$${plan.total_cost_delta} (simulated providers)`)
        pushLog(`// status=succeeded steps=${(result.steps || []).length}`)
        try {
          pushLog(`draft_notifications({ plan_id: "${plan.plan_id}" })`)
          const draft = await mcp.draftNotifications(plan.plan_id)
          setNotificationDraft(draft)
          pushLog(`// draft ready hash=${String(draft.content_hash).slice(0, 16)}…`)
        } catch (e: any) {
          pushLog(`// draft_notifications note: ${e?.message || e}`)
        }
      } else if (result.status === 'failed_rolled_back' || result.status === 'partially_failed') {
        setStage('partial_failure')
        announce(`Backend reported ${result.status} · plan ${plan.plan_id}`)
        pushLog(`// status=${result.status} compensations=${(result.compensations || []).length}`)
      } else {
        setStage('review')
        setBackendError(`Unexpected status: ${result.status || 'unknown'}`)
        announce(`Unexpected execution status: ${result.status || 'unknown'}`)
        pushLog(`// unexpected status=${result.status}`)
      }
    } catch (err: any) {
      setStage('review')
      const msg = err?.message || String(err) || 'Unknown backend error'
      setBackendError(msg)
      announce(`Recovery failed: ${msg}. No changes were applied.`)
      pushLog(`// ERROR ${msg}`)
    }
  }

  const sendNotificationAction = async () => {
    if (!backendPlan || !notificationDraft || sendingNotif) return
    setSendingNotif(true)
    const log = [...toolLog]
    const pushLog = (line: string) => { log.push(line); setToolLog([...log]) }
    try {
      pushLog(`approve_notifications({ plan_id: "${backendPlan.plan_id}", draft_hash: "${notificationDraft.content_hash.slice(0, 16)}…" })`)
      const ap = await mcp.approveNotifications(backendPlan.plan_id, notificationDraft.content_hash)
      if (!ap.ok) throw new Error(ap.message || ap.error || 'Notification approval failed')

      pushLog(`send_notifications({ plan_id: "${backendPlan.plan_id}", draft_hash: "${notificationDraft.content_hash.slice(0, 16)}…" })`)
      const sent = await mcp.sendNotifications(backendPlan.plan_id, notificationDraft.content_hash)
      if (!sent.ok) throw new Error(sent.message || sent.error || 'Failed to send notification')

      setNotificationSent(true)
      announce(`Notification sent to Sam (${(sent.sent || []).length} message delivered via mock provider)`)
      pushLog(`// notification sent provider=simulated count=${(sent.sent || []).length}`)
    } catch (e: any) {
      const msg = e?.message || String(e)
      announce(`Could not send notification: ${msg}`)
      pushLog(`// notification error: ${msg}`)
    } finally {
      setSendingNotif(false)
    }
  }

  const resetDemo = () => {
    setStage('review')
    setRawCallsOpen(false)
    setNotificationSent(false)
    setNotificationDraft(null)
    setBackendResult(null)
    setBackendPlan(null)
    setBackendError(null)
    announce('Demo reset to the approval checkpoint.')
  }

  const deletePreferencesAction = async () => {
    setPreferences(emptyPreferences)
    setPreferencesDeleted(true)
    try {
      await Promise.all([
        mcp.deletePreference('preferred_airline'),
        mcp.deletePreference('seat'),
        mcp.deletePreference('max_additional_cost'),
        mcp.deletePreference('avoid_overnight'),
      ])
      announce('Saved preferences deleted from backend database.')
    } catch {
      announce('Saved preferences cleared locally.')
    }
  }

  const restorePreferencesAction = async () => {
    setPreferences(initialPreferences)
    setPreferencesDeleted(false)
    try {
      await Promise.all([
        mcp.savePreference('preferred_airline', 'Example Air'),
        mcp.savePreference('seat', 'aisle'),
        mcp.savePreference('max_additional_cost', 3000),
        mcp.savePreference('avoid_overnight', true),
      ])
      announce('Saved preferences restored on database.')
    } catch {
      announce('Saved preferences restored.')
    }
  }

  const togglePreference = async (key: keyof typeof preferences, values: string[]) => {
    const current = preferences[key]
    const next = values.find((value) => value !== current) ?? current
    setPreferencesDeleted(false)
    setPreferences((previous) => ({ ...previous, [key]: next }))
    const keyMap: Record<string, string> = {
      airline: 'preferred_airline',
      seat: 'seat',
      maxDelta: 'max_additional_cost',
      overnight: 'avoid_overnight',
    }
    const backendKey = keyMap[key]
    if (!backendKey) return
    let value: string | number | boolean = next
    if (key === 'seat') value = next.toLowerCase().includes('window') ? 'window' : 'aisle'
    if (key === 'maxDelta') value = Number(String(next).replace(/[^0-9]/g, '')) || 3000
    if (key === 'overnight') value = !String(next).toLowerCase().includes('okay')
    if (key === 'airline') value = next.includes('SAS') ? 'Example Air' : next
    setPrefsLoading(true)
    try {
      await mcp.savePreference(backendKey, value)
      announce(`Saved preference ${backendKey} on server.`)
    } catch (e: any) {
      announce(`Could not save preference: ${e?.message || 'backend offline'}`)
    } finally {
      setPrefsLoading(false)
    }
  }

  const activityEvents = useMemo(() => {
    const events: ToolEvent[] = [
      { id: 'status', time: '14:32:08', tier: 'read', name: 'get_disruption', detail: 'SK 908 delay detected (illustrative mock scenario)' },
      { id: 'impact', time: '14:32:09', tier: 'read', name: 'get_trip_impact', detail: 'Connection, hotel check-in, ride at risk' },
      { id: 'rank', time: '14:32:11', tier: 'propose', name: 'rank_alternatives', detail: 'Scoring alternative flights against preferences' },
      {
        id: 'plan',
        time: backendPlan ? 'active' : '14:32:13',
        tier: 'propose',
        name: 'build_rescue_plan',
        detail: backendPlan
          ? `Plan v${backendPlan.version || 1} · hash ${String(backendPlan.plan_hash || '').slice(0, 8)}… (server proposal)`
          : 'Awaiting server plan proposal',
      },
      {
        id: 'approval',
        time: stage === 'review' ? 'waiting' : 'approved',
        tier: 'commit',
        name: 'approval_gate',
        detail: stage === 'review'
          ? 'Explicit traveller approval required'
          : 'Approved by user-alex · hash verified',
      },
    ]

    if (stage === 'executing') {
      events.push({
        id: 'execute',
        time: 'running',
        tier: 'commit',
        name: 'execute_rescue_plan',
        detail: 'Transaction in progress on backend…',
      })
    } else if (backendResult?.steps) {
      backendResult.steps.forEach((step: any, idx: number) => {
        const isFailed = step.status === 'failed'
        let detail = ''
        if (step.type === 'change_flight') {
          detail = isFailed
            ? `Flight change failed: ${step.message || 'error'}`
            : `${step.airline || 'Flight'} ${step.flight_number || ''} confirmed · Ref: ${step.booking_reference || 'MOCK-REF'}`
        } else if (step.type === 'reschedule_hotel') {
          detail = isFailed
            ? `Hotel reschedule failed: ${step.message || 'error'}`
            : `Hotel check-in updated · ${step.proposed_check_in || 'confirmed'}`
        } else if (step.type === 'reschedule_ride') {
          detail = isFailed
            ? `Ride failed: ${step.message || 'Simulated provider failure'}`
            : `Airport ride rescheduled · ${step.pickup_time || 'confirmed'}`
        } else if (step.type === 'draft_notification') {
          detail = `Notification draft prepared for ${step.recipient || 'contact'}`
        } else {
          detail = step.message || `Status: ${step.status}`
        }
        events.push({
          id: `step-${idx}`,
          time: `step ${step.step || idx + 1}`,
          tier: 'commit',
          name: step.type,
          detail,
        })
      })

      if (backendResult.compensations?.length) {
        backendResult.compensations.forEach((comp: any, idx: number) => {
          events.push({
            id: `comp-${idx}`,
            time: 'rollback',
            tier: 'commit',
            name: `compensate_${comp.action}`,
            detail: `Compensated ${comp.action} (${comp.status || 'success'})`,
          })
        })
      }
    }

    if (notificationSent) {
      events.push({
        id: 'message-sent',
        time: 'sent',
        tier: 'commit',
        name: 'send_notifications',
        detail: 'Delivered via simulated provider (mock dispatch)',
      })
    }
    return events
  }, [stage, backendResult, backendPlan, notificationSent])

  const eventState = (eventId: string) => {
    if (eventId === 'approval') return stage === 'review' ? 'waiting' : 'done'
    if (eventId === 'execute') return 'running'
    if (eventId.startsWith('step-')) {
      const idx = parseInt(eventId.replace('step-', ''), 10)
      const step = backendResult?.steps?.[idx]
      return step?.status === 'failed' ? 'warning' : 'done'
    }
    if (eventId.startsWith('comp-')) return 'warning'
    if (eventId === 'message-sent') return 'done'
    if (stage === 'review' && eventId === 'plan') return backendPlan ? 'done' : 'waiting'
    return 'done'
  }

  const stageLabel = stage === 'review' ? 'APPROVAL REQUIRED' : stage === 'executing' ? 'EXECUTING SAFELY' : stage === 'recovered' ? 'RECOVERY COMPLETE' : 'PARTIAL FAILURE · CAPTURED'
  const stageTone = stage === 'review' ? 'amber' : stage === 'executing' ? 'blue' : stage === 'recovered' ? 'teal' : 'coral'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header"><BrandMark /></div>
        <div className="trip-context">
          <span className="eyebrow">ACTIVE TRIP / 004</span>
          <strong>{trip.origin} <span>→</span> {trip.destination}</strong>
          <span className="mono muted">{trip.date} · {trip.code}</span>
        </div>
        <nav className="primary-nav" aria-label="Primary navigation">
          <button className="nav-item nav-item--active"><span><Icon name="pulse" size={17} /><span className="nav-label">Rescue plan</span></span><span className="nav-count">1</span></button>
          <button className="nav-item" onClick={() => announce('Itinerary view is ready for the next step.')}><span><Icon name="route" size={17} /><span className="nav-label">Itinerary</span></span></button>
          <button className="nav-item" onClick={() => setPreferencesOpen(true)}><span><Icon name="sliders" size={17} /><span className="nav-label">Preferences</span></span></button>
          <button className="nav-item" onClick={() => setRawCallsOpen((value) => !value)}><span><Icon name="audit" size={17} /><span className="nav-label">Audit log</span></span><span className="nav-live">LIVE</span></button>
        </nav>
        <div className="sidebar-footer">
          <div className="mode-card"><div className="mode-topline"><span className="live-dot" />DEMO MODE</div><p>Mock providers are on. Approval logic is real.</p><button onClick={() => announce('Travel data, providers and messaging are fictional mocks; safety logic and auditability are real.')}>What is simulated? <Icon name="arrow" size={13} /></button></div>
          <button className="profile-row" onClick={() => setPreferencesOpen(true)}><span className="avatar">AR</span><span><strong>Alex Rivera</strong><small>Traveller profile</small></span><Icon name="chevron" size={15} /></button>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="mobile-brand"><BrandMark compact /></div>
          <div className="breadcrumbs"><span>TRIPS</span><Icon name="chevron" size={12} /><strong>TRP-00419</strong><StatusChip tone="blue" dot>DEMO MODE</StatusChip></div>
          <div className="topbar-actions"><span className="sync-state"><span className="sync-dot" />All systems nominal</span><button className="icon-button" aria-label="Open preferences" onClick={() => setPreferencesOpen(true)}><Icon name="sliders" size={18} /></button><button className="avatar avatar--small" onClick={() => setPreferencesOpen(true)}>AR</button></div>
        </header>

        <div className="workspace-grid">
          <section className="stage-column">
            <section className="hero-section">
              <div className="hero-copy">
                <div className="eyebrow-row"><span className="eyebrow eyebrow--amber">LIVE DISRUPTION</span><span className="signal-line" aria-hidden="true"><i /><i /><i /><i /><i /></span><span className="mono muted">14:32 LOCAL</span></div>
                <h1>Your connection<br /><em>is at risk.</em></h1>
                <p className="hero-lede">SK 908 is delayed by <strong>1h 40m</strong>. Your Copenhagen connection is no longer safe—but the rest of your trip is still recoverable.</p>
                <div className="hero-meta"><span><Icon name="clock" size={15} />Detected 14:32</span><span><Icon name="database" size={15} />Live provider check</span><span><Icon name="shield" size={15} />You stay in control</span></div>
              </div>
              <div className="impact-card">
                <div className="impact-head"><span className="eyebrow">TRIP IMPACT</span><StatusChip tone="coral" dot>3 AT RISK</StatusChip></div>
                <div className="impact-number">+<span>1</span><small>h</small> 40<small>m</small></div>
                <p>estimated disruption window</p>
                <div className="impact-items"><span><i className="impact-icon impact-icon--coral"><Icon name="plane" size={14} /></i>Connection</span><span><i className="impact-icon impact-icon--coral"><Icon name="car" size={14} /></i>Airport ride</span><span><i className="impact-icon impact-icon--coral"><Icon name="message" size={14} /></i>Waiting person</span></div>
              </div>
            </section>

            <section className="route-card panel">
              <div className="section-heading"><div><span className="eyebrow">YOUR ROUTE</span><h2>One trip. Four moving parts.</h2></div><StatusChip tone="teal" dot>ITINERARY SYNCED</StatusChip></div>
              <div className="route-strip">
                <div className="route-stop"><span className="stop-code">{trip.originCode}</span><strong>{trip.origin}</strong><small>{trip.terminal}</small></div>
                <div className="route-middle"><div className="route-line"><span className="route-line-fill" /><i /><i /><i /></div><div className="route-note"><span className="route-note-line" /><span>CONNECTION AT RISK</span><span className="route-note-line" /></div><div className="route-flight"><Icon name="plane" size={14} />{trip.originalFlight} · {trip.originalTime} <span>→</span> {trip.revisedTime}</div></div>
                <div className="route-stop route-stop--right"><span className="stop-code">{trip.destinationCode}</span><strong>{trip.destination}</strong><small>{trip.hotel}</small></div>
              </div>
              <div className="route-bottom"><span><i className="legend-dot legend-dot--teal" />CONFIRMED <strong>Flight + hotel</strong></span><span><i className="legend-dot legend-dot--coral" />AT RISK <strong>Connection + ride + message</strong></span><span className="mono">LAST CHECK 14:32:11</span></div>
            </section>

            <section className="alternatives-section">
              <div className="section-heading section-heading--loose"><div><span className="eyebrow">RANKED ALTERNATIVES</span><h2>Three ways forward.</h2></div><button className="text-button" onClick={() => announce('Ranking is based on your saved preferences and current provider data.')}>How we rank <Icon name="arrow" size={14} /></button></div>
              <div className="preference-note"><span className="preference-icon"><Icon name="spark" size={16} /></span><span>Ranking against your saved preferences</span><span className="preference-value">{preferences.airline} · {preferences.seat.toLowerCase()} · max {preferences.maxDelta} change</span><button onClick={() => setPreferencesOpen(true)}>Edit</button></div>
              <div className="alternatives-grid">{rankedAlternatives.map((option) => <AlternativeCard key={option.id} option={option} selected={option.id === selected.id} onSelect={() => selectAlternative(option)} />)}</div>
            </section>

            <section className={`plan-card panel plan-card--${stage}`}>
              <div className="plan-header"><div><div className="eyebrow-row"><span className="eyebrow">COORDINATED RESCUE PLAN</span><span className="mono muted">{backendPlan ? `VERSION ${String(backendPlan.version || 1).padStart(2, '0')} · HASH ${String(backendPlan.plan_hash || '').slice(0, 4).toUpperCase()}…${String(backendPlan.plan_hash || '').slice(-4).toUpperCase()}` : 'PENDING PROPOSAL · SERVER HASH BOUND'}</span></div><h2>{stage === 'review' ? 'Ready for your say.' : stage === 'executing' ? 'Your plan is in motion.' : stage === 'recovered' ? 'Your trip is back on track.' : 'One step needs your attention.'}</h2><p>{stage === 'review' ? 'Review every change before anything is booked, moved or sent.' : stage === 'executing' ? 'We are running each step as a transaction. You will see the result of every action.' : stage === 'recovered' ? 'All recovery actions confirmed by backend. Notification draft ready.' : (backendResult?.message || 'The ride failed. Other steps were compensated. The message was not sent.')}</p></div><StatusChip tone={stageTone} dot>{stageLabel}</StatusChip></div>
              <div className="plan-items">
                <div className="plan-item"><span className="plan-icon plan-icon--plane"><Icon name="plane" size={17} /></span><span className="plan-item-copy"><strong>Switch flight to {selected.flight}</strong><small>{selected.airline} · {selected.departure} departure · {selected.seat}</small></span><span className="plan-item-state">{stage === 'review' ? 'PROPOSED' : stage === 'recovered' ? 'UPDATED' : 'COMPENSATED'}<small>{selected.delta > 0 ? `+$${selected.delta}` : `-$${Math.abs(selected.delta)}`}</small></span></div>
                <div className="plan-item"><span className="plan-icon plan-icon--hotel"><Icon name="hotel" size={17} /></span><span className="plan-item-copy"><strong>Move hotel check-in to 12:00</strong><small>{trip.hotel} · no rate change · room held</small></span><span className="plan-item-state plan-item-state--safe">{stage === 'partial_failure' ? 'COMPENSATED' : 'HELD'}<small>$0</small></span></div>
                <div className="plan-item"><span className="plan-icon plan-icon--car"><Icon name="car" size={17} /></span><span className="plan-item-copy"><strong>Reschedule airport ride</strong><small>{trip.ride} · {stage === 'partial_failure' ? 'Simulated provider failure' : 'pickup updated to 11:35'}</small></span><span className={`plan-item-state${stage === 'partial_failure' ? ' plan-item-state--warning' : ''}`}>{stage === 'partial_failure' ? 'FAILED' : 'READY'}<small>{stage === 'partial_failure' ? 'Failure caught' : '+$18'}</small></span></div>
                <div className="plan-item"><span className="plan-icon plan-icon--message"><Icon name="message" size={17} /></span><span className="plan-item-copy"><strong>{notificationSent ? 'Message sent to Sam' : 'Draft message to Sam'}</strong><small>“Landing at 11:05 now—ride is moved. See you soon.”</small></span><span className={`plan-item-state ${notificationSent ? 'plan-item-state--safe' : stage === 'partial_failure' ? 'plan-item-state--warning' : 'plan-item-state--safe'}`}>{notificationSent ? 'DELIVERED' : stage === 'partial_failure' ? 'NOT SENT' : 'DRAFT READY'}<small>{notificationSent ? 'Sent to Sam' : stage === 'partial_failure' ? 'Discarded' : 'Requires approval'}</small></span></div>
              </div>
              <div className="plan-total"><span><span className="eyebrow">TOTAL COST CHANGE</span><strong>{backendPlan ? `+$${backendPlan.total_cost_delta}` : '—'}</strong><small>{backendPlan ? `plan ${backendPlan.plan_id} · hash ${String(backendPlan.plan_hash).slice(0, 12)}… · simulated providers` : 'Cost appears after server proposes the plan'}</small></span><span className="plan-lock"><Icon name="lock" size={15} />Approval is bound to the exact server plan hash</span></div>
              <div className="plan-actions">
                {backendError && <p className="plan-disclaimer" style={{color:'#b45041'}}><Icon name="close" size={15} />{backendError}</p>}
                {backendResult && <p className="plan-disclaimer">Last execution: <strong>{backendResult.status}</strong>{backendResult.message ? ` — ${backendResult.message}` : ''} (providers: simulated)</p>}
                {stage === 'review' && <button className="primary-button" onClick={() => executePlan('recovered')}><Icon name="shield" size={17} />Propose, approve &amp; execute <span>→</span></button>}
                {stage === 'executing' && <button className="primary-button primary-button--busy" disabled><span className="button-spinner" />Executing safely…</button>}
                {stage === 'recovered' && <button className="primary-button primary-button--success" onClick={resetDemo}><Icon name="refresh" size={17} />Run demo again</button>}
                {stage === 'recovered' && notificationDraft && !notificationSent && <button className="secondary-button" onClick={sendNotificationAction} disabled={sendingNotif}><Icon name="message" size={15} />{sendingNotif ? 'Sending…' : 'Approve & send notification'}</button>}
                {stage === 'partial_failure' && <button className="primary-button primary-button--warning" onClick={resetDemo}><Icon name="refresh" size={17} />Review recovery again</button>}
                {stage === 'review' && <button className="secondary-button" onClick={() => executePlan('partial_failure')}><Icon name="terminal" size={15} />Run failure path</button>}
                {(stage === 'recovered' || stage === 'partial_failure') && <button className="secondary-button" onClick={() => setRawCallsOpen(true)}><Icon name="audit" size={15} />View audit trail</button>}
              </div>
              <div className="plan-disclaimer"><Icon name="shield" size={14} />No bookings or messages are sent until you approve. Server cryptographic hash protects against tampering.</div>
            </section>
          </section>

          <aside className="activity-column">
            <div className="activity-header"><div><span className="eyebrow">AGENT ACTIVITY</span><h2>What’s happening</h2></div><span className="live-pill"><i />LIVE</span></div>
            <div className="activity-card panel">
              <div className="activity-card-head"><span className="activity-pulse"><i /><i /><i /></span><div><strong>{stage === 'review' ? 'Waiting for your approval' : stage === 'executing' ? 'Executing approved plan' : stage === 'recovered' ? 'Recovery reconciled' : 'Compensation complete'}</strong><small>{stage === 'review' ? 'No commit action has run.' : 'Every step is logged and versioned.'}</small></div></div>
              <div className="event-list">{activityEvents.map((event) => {
                const state = eventState(event.id)
                return <div className={`event-row event-row--${state}`} key={event.id}><span className="event-marker">{state === 'done' ? <Icon name="check" size={11} /> : state === 'running' ? <span className="event-spinner" /> : state === 'warning' ? '!' : ''}</span><div className="event-copy"><div><strong>{event.name}</strong><TierBadge tier={event.tier} /></div><small>{event.detail}</small></div><span className="event-time mono">{event.time}</span></div>
              })}</div>
              <button className="activity-link" onClick={() => setRawCallsOpen((value) => !value)}><Icon name="terminal" size={15} />{rawCallsOpen ? 'Hide raw tool calls' : 'View raw tool calls'}<Icon name="arrow" size={14} /></button>
              {rawCallsOpen && <div className="raw-calls"><div className="raw-head"><span className="eyebrow">TOOL LOG · FROM BACKEND CALLS</span><StatusChip tone="teal" dot>LIVE</StatusChip></div>{(toolLog.length ? toolLog : ['// No tool calls yet — approve a plan to invoke the server']).map((call) => <code key={call}>{call}</code>)}</div>}
            </div>

            <div className="trust-card"><div className="trust-icon"><Icon name="shield" size={19} /></div><div><span className="eyebrow">TRUST BOUNDARY</span><strong>Approval lives on the server.</strong><p>The model can recommend. Only a validated, approved plan can execute—and changing it invalidates the approval hash.</p><button onClick={() => announce('Server enforcement: stale, expired and duplicate approvals are refused.')}>See the safety model <Icon name="arrow" size={13} /></button></div></div>
            <div className="side-stats"><div><span className="eyebrow">MEMORY</span><strong>4 preferences</strong><small>saved for next trip</small></div><div><span className="eyebrow">AUDIT</span><strong>100% logged</strong><small>commit actions tracked</small></div></div>
            <button className="preferences-link" onClick={() => setPreferencesOpen(true)}><Icon name="sliders" size={16} /><span><strong>Traveller preferences</strong><small>View, edit or delete saved choices</small></span><Icon name="chevron" size={15} /></button>
          </aside>
        </div>

        <footer className="app-footer"><span><span className="footer-mark" />Travel data, providers and messaging are fictional mocks · MCP server, approval, execution, rollback and memory are real code</span><span className="mono">MCP 2025-11-25 · BUILD 0.9.4</span></footer>
      </main>

      {preferencesOpen && <div className="drawer-backdrop" onClick={() => setPreferencesOpen(false)}><aside className="preferences-drawer" role="dialog" aria-modal="true" aria-labelledby="preferences-title" onClick={(event) => event.stopPropagation()}><div className="drawer-header"><div><span className="eyebrow">TRAVELLER MEMORY</span><h2 id="preferences-title">Preferences</h2></div><button className="icon-button icon-button--large" onClick={() => setPreferencesOpen(false)} aria-label="Close preferences"><Icon name="close" size={18} /></button></div><p className="drawer-intro">{preferencesDeleted ? 'No saved preferences are active. Restore defaults or make a new choice below.' : 'These choices shape how Trip Rescue ranks alternatives. You can edit or delete them at any time.'}</p><div className="preference-list"><PreferenceRow label="Preferred airline" value={preferences.airline} options={['SAS / Star Alliance', 'Any airline']} onChange={() => togglePreference('airline', ['SAS / Star Alliance', 'Any airline'])} /><PreferenceRow label="Seat preference" value={preferences.seat} options={['Window', 'Aisle']} onChange={() => togglePreference('seat', ['Window', 'Aisle'])} /><PreferenceRow label="Max cost change" value={preferences.maxDelta} options={['$75', '$150']} onChange={() => togglePreference('maxDelta', ['$75', '$150'])} /><PreferenceRow label="Overnight travel" value={preferences.overnight} options={['Avoid overnight flights', 'Overnight is okay']} onChange={() => togglePreference('overnight', ['Avoid overnight flights', 'Overnight is okay'])} /></div><div className="drawer-note"><Icon name="database" size={15} /><span>Saved locally for this demo. In production, these preferences are stored with the trip profile and can be deleted.</span></div><div className="drawer-actions"><button className="delete-link" onClick={deletePreferencesAction}>Delete saved preferences</button><button className="restore-link" onClick={restorePreferencesAction}>Restore defaults</button></div></aside></div>}
      {toast && <div className="toast" role="status"><span className="toast-icon"><Icon name="check" size={14} /></span>{toast}</div>}
    </div>
  )
}

function PreferenceRow({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: () => void }) {
  return <button className="preference-row" onClick={onChange}><span><span className="eyebrow">{label}</span><strong>{value}</strong></span><span className="preference-switch"><span className="preference-switch-dot" /><Icon name="chevron" size={14} /></span></button>
}

export default App
