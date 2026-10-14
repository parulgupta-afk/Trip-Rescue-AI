import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  alternatives,
  initialPreferences,
  rawCalls,
  toolEvents,
  trip,
  type Alternative,
  type DemoStage,
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
    announce('Calling rescue server · propose → approve → execute…')
    const flightId = FLIGHT_MAP[selectedId] || 'FLIGHT-A'
    const forceFail = outcome === 'partial_failure' ? 'reschedule_ride' : undefined
    try {
      const plan = await mcp.proposeRescuePlan(flightId)
      if (plan.error || !plan.plan_id) throw new Error(plan.error || 'Plan failed')
      const approval = await mcp.approveRescuePlan(plan.plan_id, plan.plan_hash)
      if (!approval.ok) throw new Error(approval.message || approval.error || 'Approval failed')
      const result = await mcp.executeRescuePlan(plan.plan_id, forceFail)
      const finalStage: DemoStage =
        result.status === 'succeeded' ? 'recovered' : 'partial_failure'
      setStage(finalStage)
      announce(
        finalStage === 'recovered'
          ? `Recovery complete · plan ${plan.plan_id} · all steps succeeded.`
          : `Partial failure · plan ${plan.plan_id} · compensations applied where possible.`,
      )
    } catch (err: any) {
      // Never claim success without backend confirmation
      setStage('review')
      const msg = err?.message || String(err) || 'Unknown backend error'
      announce(`Recovery failed: ${msg}. No changes were applied.`)
    }
  }

  const resetDemo = () => {
    setStage('review')
    setRawCallsOpen(false)
    announce('Demo reset to the approval checkpoint.')
  }

  const togglePreference = (key: keyof typeof preferences, values: string[]) => {
    const current = preferences[key]
    const next = values.find((value) => value !== current) ?? current
    setPreferencesDeleted(false)
    setPreferences((previous) => ({ ...previous, [key]: next }))
  }

  const activityEvents = useMemo(() => {
    const events = [...toolEvents]
    if (stage !== 'review') events.push({ id: 'execute', time: stage === 'executing' ? 'running' : '14:32:16', tier: 'commit' as ToolTier, name: 'execute_plan', detail: stage === 'executing' ? 'Transaction in progress · 2 of 4 steps' : 'Receipt 3b77… · plan committed' })
    if (stage === 'partial_failure') {
      events.push({ id: 'compensate', time: '14:32:18', tier: 'commit' as ToolTier, name: 'compensate_ride', detail: 'Ride cancelled · $18 refunded' })
      events.push({ id: 'message-sent', time: '14:32:19', tier: 'commit' as ToolTier, name: 'send_message', detail: 'Delivered · cannot be undone' })
    }
    return events
  }, [stage])

  const eventState = (eventId: string) => {
    if (stage === 'review') return eventId === 'approval' ? 'waiting' : 'done'
    if (stage === 'executing') return eventId === 'approval' || eventId === 'execute' ? (eventId === 'execute' ? 'running' : 'done') : 'done'
    if (stage === 'recovered') return 'done'
    if (eventId === 'message-sent') return 'warning'
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
              <div className="plan-header"><div><div className="eyebrow-row"><span className="eyebrow">COORDINATED RESCUE PLAN</span><span className="mono muted">VERSION 03 · HASH 8D2F…A91C</span></div><h2>{stage === 'review' ? 'Ready for your say.' : stage === 'executing' ? 'Your plan is in motion.' : stage === 'recovered' ? 'Your trip is back on track.' : 'One step needs your attention.'}</h2><p>{stage === 'review' ? 'Review every change before anything is booked, moved or sent.' : stage === 'executing' ? 'We are running each step as a transaction. You will see the result of every action.' : stage === 'recovered' ? 'All reversible steps reconciled. Your updated itinerary is ready to travel.' : 'The ride was compensated. The message was delivered and cannot be undone.'}</p></div><StatusChip tone={stageTone} dot>{stageLabel}</StatusChip></div>
              <div className="plan-items">
                <div className="plan-item"><span className="plan-icon plan-icon--plane"><Icon name="plane" size={17} /></span><span className="plan-item-copy"><strong>Switch flight to {selected.flight}</strong><small>{selected.airline} · {selected.departure} departure · {selected.seat}</small></span><span className="plan-item-state">{stage === 'review' ? 'PROPOSED' : 'UPDATED'}<small>{selected.delta > 0 ? `+$${selected.delta}` : `-$${Math.abs(selected.delta)}`}</small></span></div>
                <div className="plan-item"><span className="plan-icon plan-icon--hotel"><Icon name="hotel" size={17} /></span><span className="plan-item-copy"><strong>Move hotel check-in to 12:00</strong><small>{trip.hotel} · no rate change · room held</small></span><span className="plan-item-state plan-item-state--safe">HELD<small>$0</small></span></div>
                <div className="plan-item"><span className="plan-icon plan-icon--car"><Icon name="car" size={17} /></span><span className="plan-item-copy"><strong>Reschedule airport ride</strong><small>{trip.ride} · pickup updated to 11:35</small></span><span className={`plan-item-state${stage === 'partial_failure' ? ' plan-item-state--warning' : ''}`}>{stage === 'partial_failure' ? 'COMPENSATED' : 'READY'}<small>{stage === 'partial_failure' ? '$18 refunded' : '+$18'}</small></span></div>
                <div className="plan-item"><span className="plan-icon plan-icon--message"><Icon name="message" size={17} /></span><span className="plan-item-copy"><strong>{stage === 'partial_failure' ? 'Message delivered to Maya' : 'Draft message to Maya'}</strong><small>“Landing at 11:05 now—ride is moved. See you soon.”</small></span><span className={`plan-item-state ${stage === 'partial_failure' ? 'plan-item-state--warning' : 'plan-item-state--safe'}`}>{stage === 'partial_failure' ? 'DELIVERED' : 'DRAFTED'}<small>{stage === 'partial_failure' ? 'Cannot undo' : 'Not sent'}</small></span></div>
              </div>
              <div className="plan-total"><span><span className="eyebrow">TOTAL COST CHANGE</span><strong>{selected.delta + 18 >= 0 ? '+' : '-'}${Math.abs(selected.delta + 18)}.00</strong><small>calculated by rescue server · taxes included</small></span><span className="plan-lock"><Icon name="lock" size={15} />Approval is bound to this exact plan</span></div>
              <div className="plan-actions">
                {stage === 'review' && <button className="primary-button" onClick={() => executePlan('recovered')}><Icon name="shield" size={17} />Approve exact plan <span>→</span></button>}
                {stage === 'executing' && <button className="primary-button primary-button--busy" disabled><span className="button-spinner" />Executing safely…</button>}
                {stage === 'recovered' && <button className="primary-button primary-button--success" onClick={resetDemo}><Icon name="refresh" size={17} />Run demo again</button>}
                {stage === 'partial_failure' && <button className="primary-button primary-button--warning" onClick={resetDemo}><Icon name="refresh" size={17} />Review recovery again</button>}
                {stage === 'review' && <button className="secondary-button" onClick={() => executePlan('partial_failure')}><Icon name="terminal" size={15} />Run failure path</button>}
                {(stage === 'recovered' || stage === 'partial_failure') && <button className="secondary-button" onClick={() => setRawCallsOpen(true)}><Icon name="audit" size={15} />View audit trail</button>}
              </div>
              <div className="plan-disclaimer"><Icon name="shield" size={14} />No bookings or messages are sent until you approve. Demo approval token expires in 09:42; the server re-checks the plan hash.</div>
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
              {rawCallsOpen && <div className="raw-calls"><div className="raw-head"><span className="eyebrow">MCP STREAM · READ ONLY</span><StatusChip tone="teal" dot>VALIDATED</StatusChip></div>{(stage === 'review' ? rawCalls : rawCalls.map((call) => call.replace(' // blocked until approval', ' // approval hash verified'))).concat(stage === 'partial_failure' ? ['commit.compensate_ride({ ride_id: "RIDE-882" }) // compensated', 'commit.send_message({ draft_id: "MSG-22" }) // delivered · irreversible'] : []).map((call) => <code key={call}>{call}</code>)}</div>}
            </div>

            <div className="trust-card"><div className="trust-icon"><Icon name="shield" size={19} /></div><div><span className="eyebrow">TRUST BOUNDARY</span><strong>Approval lives on the server.</strong><p>The model can recommend. Only a validated, approved plan can execute—and changing it invalidates the approval hash.</p><button onClick={() => announce('Server enforcement: stale, expired and duplicate approvals are refused.')}>See the safety model <Icon name="arrow" size={13} /></button></div></div>
            <div className="side-stats"><div><span className="eyebrow">MEMORY</span><strong>4 preferences</strong><small>saved for next trip</small></div><div><span className="eyebrow">AUDIT</span><strong>100% logged</strong><small>commit actions tracked</small></div></div>
            <button className="preferences-link" onClick={() => setPreferencesOpen(true)}><Icon name="sliders" size={16} /><span><strong>Traveller preferences</strong><small>View, edit or delete saved choices</small></span><Icon name="chevron" size={15} /></button>
          </aside>
        </div>

        <footer className="app-footer"><span><span className="footer-mark" />Travel data, providers and messaging are fictional mocks · MCP server, approval, execution, rollback and memory are real code</span><span className="mono">MCP 2025-11-25 · BUILD 0.9.4</span></footer>
      </main>

      {preferencesOpen && <div className="drawer-backdrop" onClick={() => setPreferencesOpen(false)}><aside className="preferences-drawer" role="dialog" aria-modal="true" aria-labelledby="preferences-title" onClick={(event) => event.stopPropagation()}><div className="drawer-header"><div><span className="eyebrow">TRAVELLER MEMORY</span><h2 id="preferences-title">Preferences</h2></div><button className="icon-button icon-button--large" onClick={() => setPreferencesOpen(false)} aria-label="Close preferences"><Icon name="close" size={18} /></button></div><p className="drawer-intro">{preferencesDeleted ? 'No saved preferences are active. Restore defaults or make a new choice below.' : 'These choices shape how Trip Rescue ranks alternatives. You can edit or delete them at any time.'}</p><div className="preference-list"><PreferenceRow label="Preferred airline" value={preferences.airline} options={['SAS / Star Alliance', 'Any airline']} onChange={() => togglePreference('airline', ['SAS / Star Alliance', 'Any airline'])} /><PreferenceRow label="Seat preference" value={preferences.seat} options={['Window', 'Aisle']} onChange={() => togglePreference('seat', ['Window', 'Aisle'])} /><PreferenceRow label="Max cost change" value={preferences.maxDelta} options={['$75', '$150']} onChange={() => togglePreference('maxDelta', ['$75', '$150'])} /><PreferenceRow label="Overnight travel" value={preferences.overnight} options={['Avoid overnight flights', 'Overnight is okay']} onChange={() => togglePreference('overnight', ['Avoid overnight flights', 'Overnight is okay'])} /></div><div className="drawer-note"><Icon name="database" size={15} /><span>Saved locally for this demo. In production, these preferences are stored with the trip profile and can be deleted.</span></div><div className="drawer-actions"><button className="delete-link" onClick={() => { setPreferences(emptyPreferences); setPreferencesDeleted(true); announce('Saved preferences deleted from this demo.') }}>Delete saved preferences</button><button className="restore-link" onClick={() => { setPreferences(initialPreferences); setPreferencesDeleted(false); announce('Saved preferences restored for this demo.') }}>Restore defaults</button></div></aside></div>}
      {toast && <div className="toast" role="status"><span className="toast-icon"><Icon name="check" size={14} /></span>{toast}</div>}
    </div>
  )
}

function PreferenceRow({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: () => void }) {
  return <button className="preference-row" onClick={onChange}><span><span className="eyebrow">{label}</span><strong>{value}</strong></span><span className="preference-switch"><span className="preference-switch-dot" /><Icon name="chevron" size={14} /></span></button>
}

export default App
