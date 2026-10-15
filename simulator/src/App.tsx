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

const formatTime = (ts: string | null | undefined): string => {
  if (!ts) return '—'
  if (ts.includes('T')) {
    const timePart = ts.split('T')[1]
    return timePart.slice(0, 5)
  }
  return ts
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
  const [notificationStatus, setNotificationStatus] = useState<
    'idle' | 'drafted' | 'approved' | 'sending' | 'sent' | 'uncertain' | 'failed'
  >('idle')
  const [sendingNotif, setSendingNotif] = useState(false)
  const [toolLog, setToolLog] = useState<string[]>([])
  const [backendError, setBackendError] = useState<string | null>(null)
  const [liveTrip, setLiveTrip] = useState<any>(null)
  const [liveDisruption, setLiveDisruption] = useState<any>(null)
  const [liveAlternatives, setLiveAlternatives] = useState<any[]>([])
  const [selectedFlightId, setSelectedFlightId] = useState('FLIGHT-A')
  const [approvalInfo, setApprovalInfo] = useState<any>(null)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [prefsLoading, setPrefsLoading] = useState(false)

  // Sync preferences from server on mount
  useEffect(() => {
    let active = true
    async function bootstrap() {
      try {
        const base = String((import.meta as any).env?.VITE_MCP_URL || 'http://localhost:8000').replace(/\/$/, ''); const health = await fetch(base + '/health').then(r => r.json()).catch(() => null)
        if (!active) return
        setBackendOnline(!!health && health.status === 'ok')
      } catch {
        if (active) setBackendOnline(false)
      }
      try {
        const [trip, status, alts, prefs] = await Promise.all([
          mcp.getTrip(),
          mcp.checkFlightStatus(),
          mcp.searchAlternatives(),
          mcp.getPreferences(),
        ])
        if (!active) return
        if (trip && !trip.error) setLiveTrip(trip)
        if (status && !status.error) setLiveDisruption(status)
        if (alts?.alternatives) {
          setLiveAlternatives(alts.alternatives)
          if (alts.alternatives[0]?.id) setSelectedFlightId(alts.alternatives[0].id)
        }
        if (prefs && !prefs.error) {
          setPreferences({
            airline: String(prefs.preferred_airline?.value ?? initialPreferences.airline),
            seat: String(prefs.seat?.value ?? initialPreferences.seat),
            maxDelta: prefs.max_additional_cost?.value != null ? `$${prefs.max_additional_cost.value}` : initialPreferences.maxDelta,
            overnight: prefs.avoid_overnight?.value === false ? 'Overnight is okay' : initialPreferences.overnight,
            notifications: initialPreferences.notifications,
          })
        }
        setBackendOnline(true)
      } catch {
        if (active) setBackendOnline(false)
      }
    }
    bootstrap()
    return () => { active = false }
  }, [])

  const rankedAlternativesStatic = useMemo(() => {
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

  const displayAlternatives = useMemo(() => {
    if (liveAlternatives.length) {
      const accents = ['#f6b73c', '#3f5bf6', '#2d9c8a']
      const origCode = liveTrip?.segments?.[0]?.origin || 'DEL'
      const destCode = liveTrip?.segments?.slice(-1)[0]?.destination || 'JFK'
      return liveAlternatives.map((a: any, idx: number) => ({
        id: a.id,
        airline: a.airline,
        code: (a.airline || '').slice(0, 2).toUpperCase(),
        flight: a.flight_number,
        route: `${origCode} → ${destCode}`,
        departure: formatTime(a.departure),
        arrival: formatTime(a.arrival),
        duration: a.overnight ? 'overnight' : 'day flight',
        stops: 'Direct / 1-stop',
        seat: a.seat_available ? `${a.seat_available} seat` : 'assigned',
        price: a.extra_cost === 0 ? '$0' : `+$${a.extra_cost}`,
        delta: a.extra_cost,
        fit: a.why || (a.extra_cost === 0 ? 'No extra cost' : 'Alternative option'),
        tags: [
          ...(a.overnight ? ['OVERNIGHT'] : ['DAY']),
          ...(a.extra_cost === 0 ? ['INCLUDED'] : a.extra_cost <= 1500 ? ['BUDGET'] : ['PREMIUM']),
          ...(a.seat_available ? [`${a.seat_available.toUpperCase()} SEAT`] : []),
        ],
        accent: accents[idx % accents.length],
      }))
    }
    return rankedAlternativesStatic
  }, [liveAlternatives, liveTrip, rankedAlternativesStatic])

  const selected = useMemo(
    () => displayAlternatives.find((option: any) => option.id === selectedFlightId || option.id === selectedId) ?? displayAlternatives[0] ?? alternatives[0],
    [displayAlternatives, selectedFlightId, selectedId],
  )
  const isBusy = stage === 'executing' || prefsLoading

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

  const selectAlternative = (option: any) => {
    if (isBusy) return
    const targetFlightId = FLIGHT_MAP[option.id] || option.id
    setSelectedId(option.id)
    setSelectedFlightId(targetFlightId)
    if (stage !== 'review') setStage('review')
    announce(`${option.airline} ${option.flight} is now the active rescue option.`)
  }

  const proposePlan = async () => {
    if (isBusy) return
    setBackendError(null)
    setBackendResult(null)
    setApprovalInfo(null)
    setBackendPlan(null)
    const log: string[] = []
    const pushLog = (line: string) => { log.push(line); setToolLog([...log]) }
    announce('Requesting rescue plan from server (no approval, no execution)…')
    try {
      pushLog(`propose_rescue_plan({ selected_flight_id: "${selectedFlightId}" })`)
      const plan = await mcp.proposeRescuePlan(selectedFlightId)
      if (plan.error || !plan.plan_id) throw new Error(plan.error || 'Plan proposal failed')
      setBackendPlan(plan)
      setStage('proposed')
      pushLog(`// plan_id=${plan.plan_id} hash=${String(plan.plan_hash).slice(0, 16)}… cost=+${plan.total_cost_delta}`)
      announce(`Plan ${plan.plan_id} ready for review. Nothing has been approved or executed.`)
    } catch (err: any) {
      setStage('review')
      const msg = err?.message || String(err)
      setBackendError(msg)
      announce(`Proposal failed: ${msg}`)
      pushLog(`// ERROR ${msg}`)
    }
  }

  const approvePlan = async () => {
    if (isBusy || !backendPlan?.plan_id || !backendPlan?.plan_hash) return
    setBackendError(null)
    const log = [...toolLog]
    const pushLog = (line: string) => { log.push(line); setToolLog([...log]) }
    announce('Submitting approval for exact plan hash…')
    try {
      pushLog(`approve_rescue_plan({ plan_id: "${backendPlan.plan_id}" })`)
      const approval = await mcp.approveRescuePlan(backendPlan.plan_id, backendPlan.plan_hash)
      if (!approval.ok) throw new Error(approval.message || approval.error || 'Approval failed')
      setApprovalInfo(approval)
      setStage('approved')
      pushLog(`// approved expires=${approval.expires_at || 'n/a'}`)
      announce('Plan approved on server. Execution still requires a separate step.')
    } catch (err: any) {
      const msg = err?.message || String(err)
      setBackendError(msg)
      announce(`Approval failed: ${msg}`)
      pushLog(`// ERROR ${msg}`)
    }
  }

  const executeApprovedPlan = async (forceFail?: string) => {
    if (isBusy || !backendPlan?.plan_id) return
    if (stage !== 'approved') {
      announce('Approve the plan before executing.')
      return
    }
    setStage('executing')
    setBackendError(null)
    const log = [...toolLog]
    const pushLog = (line: string) => { log.push(line); setToolLog([...log]) }
    announce('Executing approved plan on server…')
    try {
      pushLog(`execute_rescue_plan({ plan_id: "${backendPlan.plan_id}"${forceFail ? `, force_fail: "${forceFail}"` : ''} })`)
      const result = await mcp.executeRescuePlan(backendPlan.plan_id, forceFail)
      setBackendResult(result)
      if (result.status === 'succeeded') {
        setStage('recovered')
        announce(`Backend confirmed success · plan ${backendPlan.plan_id}`)
      } else if (result.status === 'failed_rolled_back' || result.status === 'partially_failed') {
        setStage('partial_failure')
        announce(`Backend reported ${result.status}`)
      } else {
        setStage('uncertain')
        setBackendError(`Unexpected status: ${result.status || 'unknown'}`)
        announce(`Unresolved status: ${result.status}`)
      }
      pushLog(`// status=${result.status}`)
    } catch (err: any) {
      const msg = err?.message || String(err)
      pushLog(`// ERROR ${msg}`)
      try {
        const status = await mcp.getPlanStatus(backendPlan.plan_id)
        setBackendResult(status)
        if (status.status === 'succeeded') {
          setStage('recovered')
          announce('Network error on response, but plan status is succeeded on server.')
        } else if (status.status === 'executing') {
          setStage('uncertain')
          setBackendError('Execution may still be in progress; status is unresolved.')
          announce('Could not confirm completion. Query plan status before retrying.')
        } else {
          setStage('uncertain')
          setBackendError(msg)
          announce(`Network error after request. Server status: ${status.status}. Do not assume success or failure.`)
        }
      } catch {
        setStage('uncertain')
        setBackendError(msg)
        announce(`Network error: ${msg}. Outcome unknown — not claiming "no changes applied".`)
      }
    }
  }


  const draftNotificationAction = async () => {
    if (!backendPlan?.plan_id || sendingNotif) return
    setSendingNotif(true)
    try {
      const draft = await mcp.draftNotifications(backendPlan.plan_id)
      if (draft.error || draft.ok === false) throw new Error(draft.message || draft.error || 'Draft failed')
      setNotificationDraft(draft)
      setNotificationStatus('drafted')
      announce('Notification draft loaded from server. Review the body before approving.')
    } catch (e: any) {
      announce(`Draft failed: ${e?.message || 'error'}`)
    } finally {
      setSendingNotif(false)
    }
  }

  const approveNotificationAction = async () => {
    if (!backendPlan?.plan_id || !notificationDraft?.content_hash || sendingNotif) return
    setSendingNotif(true)
    try {
      const ap = await mcp.approveNotifications(backendPlan.plan_id, notificationDraft.content_hash)
      if (!ap.ok) throw new Error(ap.message || ap.error || 'Approval failed')
      setNotificationDraft({ ...notificationDraft, approved: true, approval: ap })
      setNotificationStatus('approved')
      announce('Notification draft approved on server. Sending still requires a separate step.')
    } catch (e: any) {
      announce(`Notification approval failed: ${e?.message || 'error'}`)
    } finally {
      setSendingNotif(false)
    }
  }

  const sendNotificationAction = async () => {
    if (!backendPlan?.plan_id || !notificationDraft?.content_hash || sendingNotif) return
    if (!notificationDraft.approved) {
      announce('Approve the notification draft before sending.')
      return
    }
    setSendingNotif(true)
    setNotificationStatus('sending')
    try {
      const sent = await mcp.sendNotifications(backendPlan.plan_id, notificationDraft.content_hash)
      if (sent.status === 'uncertain') {
        setNotificationStatus('uncertain')
        announce('Notification outcome uncertain — delivery not confirmed. Reconciliation required.')
      } else if (!sent.ok || sent.status === 'failed') {
        setNotificationStatus('failed')
        throw new Error(sent.message || sent.error || 'Send failed')
      } else {
        setNotificationSent(true)
        setNotificationStatus('sent')
        announce('Notification send confirmed by server (simulated provider).')
      }
    } catch (e: any) {
      const msg = e?.message || 'error'
      if (msg.includes('uncertain')) {
        setNotificationStatus('uncertain')
      } else {
        setNotificationStatus('failed')
      }
      announce(`Send failed: ${msg}. Do not assume delivery or redispatch.`)
    } finally {
      setSendingNotif(false)
    }
  }

  const resetDemo = () => {
    setStage('review')
    setRawCallsOpen(false)
    setNotificationSent(false)
    setNotificationDraft(null)
    setNotificationStatus('idle')
    setBackendResult(null)
    setBackendPlan(null)
    setBackendError(null)
    setApprovalInfo(null)
    announce('UI reset to review. Backend plan history is unchanged.')
  }

  const deletePreferencesAction = async () => {
    try {
      await Promise.all([
        mcp.deletePreference('preferred_airline'),
        mcp.deletePreference('seat'),
        mcp.deletePreference('max_additional_cost'),
        mcp.deletePreference('avoid_overnight'),
      ])
      setPreferences(emptyPreferences)
      setPreferencesDeleted(true)
      announce('Saved preferences deleted from backend database.')
    } catch (e: any) {
      announce(`Could not delete preferences on server: ${e?.message || 'backend offline'}. UI unchanged.`)
    }
  }

  const restorePreferencesAction = async () => {
    try {
      await Promise.all([
        mcp.savePreference('preferred_airline', 'Example Air'),
        mcp.savePreference('seat', 'aisle'),
        mcp.savePreference('max_additional_cost', 3000),
        mcp.savePreference('avoid_overnight', true),
      ])
      setPreferences(initialPreferences)
      setPreferencesDeleted(false)
      announce('Saved preferences restored on database.')
    } catch (e: any) {
      announce(`Could not restore preferences on server: ${e?.message || 'backend offline'}. UI unchanged.`)
    }
  }

  const togglePreference = async (key: keyof typeof preferences, values: string[]) => {
    const current = preferences[key]
    const next = values.find((value) => value !== current) ?? current
    const previousValue = current
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
      setPreferences((previous) => ({ ...previous, [key]: previousValue })); announce(`Could not save preference: ${e?.message || 'backend offline'}. Reverted display.`)
    } finally {
      setPrefsLoading(false)
    }
  }

  const activityEvents = useMemo(() => {
    const origCode = liveTrip?.segments?.[0]?.origin || 'DEL'
    const destCode = liveTrip?.segments?.slice(-1)[0]?.destination || 'JFK'
    const events: ToolEvent[] = [
      {
        id: 'status',
        time: liveDisruption?.original_departure ? formatTime(liveDisruption.original_departure) : '18:00',
        tier: 'read',
        name: 'check_flight_status',
        detail: liveDisruption?.disrupted
          ? `${liveDisruption.flight_number} delayed ${liveDisruption.delay_hours}h · ${liveDisruption.affected?.length || 0} downstream items at risk (simulated)`
          : liveTrip
            ? `Itinerary loaded for ${liveTrip.id} (${origCode} → ${destCode})`
            : 'Illustrative scenario row (demo fallback)',
      },
      {
        id: 'impact',
        time: '18:01',
        tier: 'read',
        name: 'get_trip_impact',
        detail: liveDisruption?.affected?.length
          ? `${liveDisruption.affected.map((a: any) => a.type === 'hotel' ? 'Hotel check-in' : a.type === 'ride' ? 'Airport ride' : a.type === 'connection' ? 'Connection' : a.type).join(', ')} require schedule realignment`
          : 'Connection, hotel check-in, ride at risk',
      },
      {
        id: 'rank',
        time: '18:02',
        tier: 'propose',
        name: 'search_alternatives',
        detail: liveAlternatives.length
          ? `${liveAlternatives.length} alternative flights ranked against traveller preferences`
          : 'Scoring alternative flights against preferences',
      },
      {
        id: 'plan',
        time: backendPlan ? 'active' : 'waiting',
        tier: 'propose',
        name: 'propose_rescue_plan',
        detail: backendPlan
          ? `Plan v${backendPlan.version || 1} · hash ${String(backendPlan.plan_hash || '').slice(0, 8)}… (server proposal)`
          : 'Awaiting server plan proposal',
      },
      {
        id: 'approval',
        time: (stage === 'review' || stage === 'proposed') ? 'waiting' : 'approved',
        tier: 'commit',
        name: 'approve_rescue_plan',
        detail: stage === 'review'
          ? 'Explicit traveller approval required before execution'
          : stage === 'proposed'
            ? 'Plan proposed on server — awaiting explicit approval'
            : `Approved by user-alex · hash ${String(backendPlan?.plan_hash || '').slice(0, 8)}… verified`,
      },
    ]

    if (stage === 'executing') {
      events.push({
        id: 'execute',
        time: 'running',
        tier: 'commit',
        name: 'execute_rescue_plan',
        detail: 'Transaction in progress on backend with active lease renewal…',
      })
    } else if (backendResult?.steps) {
      backendResult.steps.forEach((step: any, idx: number) => {
        const isFailed = step.status === 'failed' || step.status === 'interrupted' || step.status === 'uncertain'
        let detail = ''
        if (step.type === 'change_flight') {
          detail = isFailed
            ? `Flight change ${step.status}: ${step.message || 'error'}`
            : `${step.airline || 'Flight'} ${step.flight_number || ''} confirmed · Ref: ${step.booking_reference || 'MOCK-REF'}`
        } else if (step.type === 'reschedule_hotel') {
          detail = isFailed
            ? `Hotel reschedule ${step.status}: ${step.message || 'error'}`
            : `Hotel check-in updated · ${step.proposed_check_in || 'confirmed'}`
        } else if (step.type === 'reschedule_ride') {
          detail = isFailed
            ? `Ride ${step.status}: ${step.message || 'Simulated provider failure'}`
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

    if (notificationDraft) {
      events.push({
        id: 'notif-draft',
        time: 'drafted',
        tier: 'read',
        name: 'draft_notifications',
        detail: `Draft prepared for ${(notificationDraft.drafts || [])[0]?.recipient || 'contact'} · hash ${String(notificationDraft.content_hash || '').slice(0, 8)}…`,
      })
    }

    if (notificationDraft?.approved) {
      events.push({
        id: 'notif-approval',
        time: 'approved',
        tier: 'commit',
        name: 'approve_notifications',
        detail: 'Notification approved on server by user-alex',
      })
    }

    if (notificationSent) {
      events.push({
        id: 'notif-sent',
        time: 'sent',
        tier: 'commit',
        name: 'send_notifications',
        detail: 'Delivered via simulated provider (mock dispatch confirmed)',
      })
    } else if (notificationStatus === 'uncertain') {
      events.push({
        id: 'notif-uncertain',
        time: 'uncertain',
        tier: 'commit',
        name: 'send_notifications',
        detail: 'Delivery outcome uncertain — reservation pending reconciliation',
      })
    } else if (notificationStatus === 'failed') {
      events.push({
        id: 'notif-failed',
        time: 'failed',
        tier: 'commit',
        name: 'send_notifications',
        detail: 'Dispatch failed — not redispatched without review',
      })
    }

    return events
  }, [stage, backendResult, backendPlan, notificationDraft, notificationSent, notificationStatus, liveDisruption, liveTrip, liveAlternatives])

  const eventState = (eventId: string): 'done' | 'running' | 'waiting' | 'warning' => {
    if (eventId === 'approval') {
      if (stage === 'review' || stage === 'proposed') return 'waiting'
      return 'done'
    }
    if (eventId === 'execute') return stage === 'executing' ? 'running' : 'done'
    if (eventId.startsWith('step-')) {
      const idx = parseInt(eventId.replace('step-', ''), 10)
      const step = backendResult?.steps?.[idx]
      if (!step) return stage === 'executing' ? 'running' : 'waiting'
      if (step.status === 'failed' || step.status === 'interrupted' || step.status === 'uncertain') return 'warning'
      if (step.status === 'running' || step.status === 'executing') return 'running'
      if (step.status === 'success' || step.status === 'succeeded') return 'done'
      return 'waiting'
    }
    if (eventId.startsWith('comp-')) return 'warning'
    if (eventId === 'notif-draft') return 'done'
    if (eventId === 'notif-approval') return 'done'
    if (eventId === 'notif-sent') return 'done'
    if (eventId === 'notif-uncertain') return 'warning'
    if (eventId === 'notif-failed') return 'warning'
    if (eventId === 'plan') {
      if (backendPlan) return 'done'
      return stage === 'review' ? 'waiting' : 'running'
    }
    return 'done'
  }

  const stageLabel =
    stage === 'review' ? 'REVIEW'
    : stage === 'proposed' ? 'PROPOSED · AWAITING APPROVAL'
    : stage === 'approved' ? 'APPROVED · READY TO EXECUTE'
    : stage === 'executing' ? 'EXECUTING'
    : stage === 'recovered' ? 'RECOVERY COMPLETE'
    : stage === 'uncertain' ? 'UNRESOLVED'
    : stage === 'partial_failure' ? 'PARTIAL FAILURE'
    : 'UNKNOWN'
  const stageTone = stage === 'recovered' ? 'teal' : (stage === 'partial_failure' || stage === 'uncertain') ? 'coral' : (stage === 'executing' || stage === 'proposed' || stage === 'approved') ? 'blue' : 'amber'

  const firstSeg = liveTrip?.segments?.[0]
  const lastSeg = liveTrip?.segments?.slice(-1)[0]
  const hotelBooking = liveTrip?.bookings?.find((b: any) => b.kind === 'hotel')
  const rideBooking = liveTrip?.bookings?.find((b: any) => b.kind === 'ride')
  const hotelName = hotelBooking?.details?.name || 'Manhattan View Hotel'
  const rideDriver = rideBooking?.details?.driver || 'Sam'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-header"><BrandMark /></div>
        <div className="trip-context">
          <span className="eyebrow">{liveTrip ? `ACTIVE TRIP / ${liveTrip.id}` : 'DEMO FALLBACK TRIP'}</span>
          <strong>{firstSeg?.origin || trip.origin} <span>→</span> {lastSeg?.destination || trip.destination}</strong>
          <span className="mono muted">{liveTrip ? '20–24 OCT 2026 · ' + liveTrip.id : `${trip.date} · ${trip.code} (DEMO)`}</span>
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
          <div className="breadcrumbs"><span>TRIPS</span><Icon name="chevron" size={12} /><strong>{liveTrip?.id || 'TRIP-100'}</strong><StatusChip tone="blue" dot>{liveTrip ? 'MOCK BACKEND' : 'DEMO FALLBACK'}</StatusChip></div>
          <div className="topbar-actions"><span className="sync-state"><span className="sync-dot" />{backendOnline === true ? 'Backend reachable' : backendOnline === false ? 'Backend offline' : 'Checking backend…'}</span><button className="icon-button" aria-label="Open preferences" onClick={() => setPreferencesOpen(true)}><Icon name="sliders" size={18} /></button><button className="avatar avatar--small" onClick={() => setPreferencesOpen(true)}>AR</button></div>
        </header>

        <div className="workspace-grid">
          <section className="stage-column">
            <section className="hero-section">
              <div className="hero-copy">
                <div className="eyebrow-row"><span className="eyebrow eyebrow--amber">{liveDisruption?.disrupted ? 'SIMULATED DISRUPTION' : 'ITINERARY STATUS'}</span><span className="signal-line" aria-hidden="true"><i /><i /><i /><i /><i /></span><span className="mono muted">{liveTrip ? 'BACKEND SYNCED' : 'DEMO FALLBACK'}</span></div>
                <h1>Your connection<br /><em>is at risk.</em></h1>
                <p className="hero-lede">{liveDisruption?.disrupted
                  ? <>{liveDisruption.flight_number || 'Flight'} delayed by <strong>{liveDisruption.delay_hours ?? 4}h</strong>. {liveDisruption.message || 'Trip recovery is available.'} <span className="muted">(simulated provider)</span></>
                  : liveTrip
                    ? <>Loaded trip <strong>{liveTrip.id}</strong> from backend. <span className="muted">(simulated)</span></>
                    : <>Waiting for backend trip data. Demo fallback values displayed.</>
                }</p>
                <div className="hero-meta">
                  <span><Icon name="clock" size={15} />Detected {liveDisruption?.original_departure ? formatTime(liveDisruption.original_departure) : '18:00'}</span>
                  <span><Icon name="database" size={15} />Simulated provider check</span>
                  <span><Icon name="shield" size={15} />You stay in control</span>
                </div>
              </div>
              <div className="impact-card">
                <div className="impact-head">
                  <span className="eyebrow">TRIP IMPACT</span>
                  <StatusChip tone="coral" dot>{liveDisruption?.affected?.length ? `${liveDisruption.affected.length} AT RISK` : '3 AT RISK (FALLBACK)'}</StatusChip>
                </div>
                <div className="impact-number">+{liveDisruption?.delay_hours ? <span>{liveDisruption.delay_hours}</span> : <span>4</span>}<small>h</small> 00<small>m</small></div>
                <p>estimated disruption window</p>
                <div className="impact-items">
                  {liveDisruption?.affected?.length ? (
                    liveDisruption.affected.map((aff: any, idx: number) => (
                      <span key={idx}>
                        <i className="impact-icon impact-icon--coral">
                          <Icon name={aff.type === 'hotel' ? 'hotel' : aff.type === 'ride' ? 'car' : aff.type === 'message' ? 'message' : 'plane'} size={14} />
                        </i>
                        {aff.type === 'connection' ? 'Connection' : aff.type === 'hotel' ? 'Hotel check-in' : aff.type === 'ride' ? 'Airport ride' : aff.type}
                      </span>
                    ))
                  ) : (
                    <>
                      <span><i className="impact-icon impact-icon--coral"><Icon name="plane" size={14} /></i>Connection</span>
                      <span><i className="impact-icon impact-icon--coral"><Icon name="car" size={14} /></i>Airport ride</span>
                      <span><i className="impact-icon impact-icon--coral"><Icon name="hotel" size={14} /></i>Hotel check-in</span>
                    </>
                  )}
                </div>
              </div>
            </section>

            <section className="route-card panel">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">YOUR ROUTE</span>
                  <h2>One trip. {liveTrip ? 'Four moving parts.' : 'Illustrative fallback.'}</h2>
                </div>
                <StatusChip tone="teal" dot>{liveTrip ? 'ITINERARY SYNCED' : 'DEMO FALLBACK'}</StatusChip>
              </div>
              <div className="route-strip">
                <div className="route-stop">
                  <span className="stop-code">{firstSeg?.origin || trip.originCode}</span>
                  <strong>{firstSeg?.origin === 'DEL' ? 'Delhi' : firstSeg?.origin || trip.origin}</strong>
                  <small>{firstSeg ? `${firstSeg.airline || 'Example Air'} · Seat ${firstSeg.seat || '12A'}` : trip.terminal}</small>
                </div>
                <div className="route-middle">
                  <div className="route-line"><span className="route-line-fill" /><i /><i /><i /></div>
                  <div className="route-note"><span className="route-note-line" /><span>CONNECTION AT RISK</span><span className="route-note-line" /></div>
                  <div className="route-flight">
                    <Icon name="plane" size={14} />
                    {firstSeg?.flight_number || trip.originalFlight} · {firstSeg?.departure_time ? formatTime(firstSeg.departure_time) : trip.originalTime} <span>→</span> {liveDisruption?.new_estimated_departure ? formatTime(liveDisruption.new_estimated_departure) : trip.revisedTime} (+{liveDisruption?.delay_hours ?? 4}h delay)
                  </div>
                </div>
                <div className="route-stop route-stop--right">
                  <span className="stop-code">{lastSeg?.destination || trip.destinationCode}</span>
                  <strong>{lastSeg?.destination === 'JFK' ? 'New York' : lastSeg?.destination || trip.destination}</strong>
                  <small>{hotelName}</small>
                </div>
              </div>
              <div className="route-bottom">
                <span><i className="legend-dot legend-dot--teal" />CONFIRMED <strong>{lastSeg?.flight_number ? `Seg 2 (${lastSeg.flight_number})` : 'Flight'} + {hotelName}</strong></span>
                <span><i className="legend-dot legend-dot--coral" />AT RISK <strong>Layover @ {firstSeg?.destination || 'LHR'} + Ride ({rideDriver})</strong></span>
                <span className="mono">{liveTrip ? 'BACKEND SYNCED (SIMULATED)' : 'DEMO FALLBACK'}</span>
              </div>
            </section>

            <section className="alternatives-section">
              <div className="section-heading section-heading--loose"><div><span className="eyebrow">RANKED ALTERNATIVES</span><h2>Three ways forward.</h2></div><button className="text-button" onClick={() => announce('Ranking is based on your saved preferences and current provider data.')}>How we rank <Icon name="arrow" size={14} /></button></div>
              <div className="preference-note"><span className="preference-icon"><Icon name="spark" size={16} /></span><span>Ranking against your saved preferences</span><span className="preference-value">{preferences.airline} · {preferences.seat.toLowerCase()} · max {preferences.maxDelta} change</span><button onClick={() => setPreferencesOpen(true)}>Edit</button></div>
              <div className="alternatives-grid">{displayAlternatives.map((option) => <AlternativeCard key={option.id} option={option} selected={option.id === selected.id} onSelect={() => selectAlternative(option)} />)}</div>
            </section>

            <section className={`plan-card panel plan-card--${stage}`}>
              <div className="plan-header">
                <div>
                  <div className="eyebrow-row">
                    <span className="eyebrow">COORDINATED RESCUE PLAN</span>
                    <span className="mono muted">
                      {backendPlan
                        ? `VERSION ${String(backendPlan.version || 1).padStart(2, '0')} · HASH ${String(backendPlan.plan_hash || '').slice(0, 4).toUpperCase()}…${String(backendPlan.plan_hash || '').slice(-4).toUpperCase()}`
                        : 'PENDING PROPOSAL · SERVER HASH BOUND'}
                    </span>
                  </div>
                  <h2>
                    {stage === 'review'
                      ? 'Ready for your say.'
                      : stage === 'proposed'
                        ? 'Plan proposed — awaiting your approval.'
                        : stage === 'approved'
                          ? 'Approved — ready to execute.'
                          : stage === 'executing'
                            ? 'Your plan is in motion.'
                            : stage === 'recovered'
                              ? 'Backend confirmed recovery.'
                              : stage === 'uncertain'
                                ? 'Outcome unresolved.'
                                : 'One step needs your attention.'}
                  </h2>
                  <p>
                    {stage === 'review'
                      ? 'Review every change before anything is booked, moved or sent.'
                      : stage === 'proposed'
                        ? backendPlan
                          ? `Plan proposed for ${selected.airline} ${selected.flight}. Review the coordinated actions below. Approval is required before execution.`
                          : 'Plan proposed on server. Review all steps.'
                        : stage === 'approved'
                          ? 'Traveller approval confirmed on backend. Execution still requires an explicit commit action.'
                          : stage === 'executing'
                            ? 'We are running each step as a transaction with active lease renewal. You will see the result of every action.'
                            : stage === 'recovered'
                              ? 'All recovery actions confirmed by backend. Notification draft is ready for review.'
                              : stage === 'partial_failure'
                                ? (backendResult?.message || 'One step failed. Compensations were applied to safely roll back confirmed actions.')
                                : stage === 'uncertain'
                                  ? (backendError || 'Execution outcome is uncertain. Query server status before re-running.')
                                  : 'Review recovery steps.'}
                  </p>
                </div>
                <StatusChip tone={stageTone} dot>{stageLabel}</StatusChip>
              </div>

              <div className="plan-items">
                {backendPlan?.actions?.length ? backendPlan.actions.map((a: any, i: number) => (
                  <div className="plan-item" key={i}>
                    <span className={`plan-icon plan-icon--${a.type?.includes('hotel') ? 'hotel' : a.type?.includes('ride') ? 'car' : a.type?.includes('message') || a.type?.includes('notification') ? 'message' : 'plane'}`}>
                      <Icon name={a.type?.includes('hotel') ? 'hotel' : a.type?.includes('ride') ? 'car' : a.type?.includes('message') || a.type?.includes('notification') ? 'message' : 'plane'} size={17} />
                    </span>
                    <span className="plan-item-copy">
                      <strong>{a.type?.replace(/_/g, ' ')}{a.flight_number ? `: ${a.flight_number}` : ''}{a.target ? ` → ${a.target}` : ''}</strong>
                      <small>{a.reason || a.body || a.proposed_check_in || a.proposed_pickup || a.airline || 'Simulated provider action'}</small>
                    </span>
                    <span className={`plan-item-state ${backendResult?.steps?.[i]?.status === 'failed' || backendResult?.steps?.[i]?.status === 'interrupted' || backendResult?.steps?.[i]?.status === 'uncertain' ? 'plan-item-state--warning' : backendResult?.steps?.[i]?.status === 'success' || backendResult?.steps?.[i]?.status === 'succeeded' ? 'plan-item-state--safe' : ''}`}>
                      {(backendResult?.steps?.[i]?.status || (stage === 'review' || stage === 'proposed' ? 'PROPOSED' : stage === 'approved' ? 'APPROVED' : 'PENDING')).toString().toUpperCase()}
                      <small>{a.cost_delta != null ? `+$${a.cost_delta}` : ''}</small>
                    </span>
                  </div>
                )) : (
                  <div className="plan-item">
                    <span className="plan-icon plan-icon--plane"><Icon name="plane" size={17} /></span>
                    <span className="plan-item-copy"><strong>No plan proposed yet</strong><small>Select an alternative and propose a plan. Server actions appear here.</small></span>
                    <span className="plan-item-state">—</span>
                  </div>
                )}
              </div>
              <div className="plan-total"><span><span className="eyebrow">TOTAL COST CHANGE</span><strong>{backendPlan ? `+$${backendPlan.total_cost_delta}` : '—'}</strong><small>{backendPlan ? `plan ${backendPlan.plan_id} · hash ${String(backendPlan.plan_hash).slice(0, 12)}… · simulated providers` : 'Cost appears after server proposes the plan'}</small></span><span className="plan-lock"><Icon name="lock" size={15} />Approval is bound to the exact server plan hash</span></div>
              <div className="plan-actions">
                {backendError && <p className="plan-disclaimer" style={{color:'#b45041'}}><Icon name="close" size={15} />{backendError}</p>}
                {backendResult && <p className="plan-disclaimer">Last execution: <strong>{backendResult.status}</strong>{backendResult.message ? ` — ${backendResult.message}` : ''} (providers: simulated)</p>}
                {stage === 'review' && <button className="primary-button" onClick={() => proposePlan()}><Icon name="shield" size={17} />Propose plan only <span>→</span></button>}
                {stage === 'executing' && <button className="primary-button primary-button--busy" disabled><span className="button-spinner" />Executing safely…</button>}
                {stage === 'recovered' && <button className="primary-button primary-button--success" onClick={resetDemo}><Icon name="refresh" size={17} />Run demo again</button>}
                {stage === 'recovered' && !notificationDraft && <button className="secondary-button" onClick={draftNotificationAction} disabled={sendingNotif}><Icon name="message" size={15} />Load notification draft</button>}
                {stage === 'recovered' && notificationDraft && (
                  <div className="plan-disclaimer" style={{textAlign:'left', maxWidth: 420}}>
                    <strong>Draft body (from server)</strong>
                    {(notificationDraft.drafts || []).map((d: any, i: number) => (
                      <p key={i} style={{margin:'0.5rem 0'}}><em>To {d.recipient}:</em> {d.body || d.subject}</p>
                    ))}
                    <small>hash {String(notificationDraft.content_hash || '').slice(0, 16)}… · simulated</small>
                  </div>
                )}
                {stage === 'recovered' && notificationDraft && !notificationDraft.approved && !notificationSent && (
                  <button className="secondary-button" onClick={approveNotificationAction} disabled={sendingNotif}>
                    <Icon name="shield" size={15} />{sendingNotif ? 'Approving…' : 'Approve notification draft'}
                  </button>
                )}
                {stage === 'recovered' && notificationDraft?.approved && !notificationSent && notificationStatus !== 'uncertain' && (
                  <button className="secondary-button" onClick={sendNotificationAction} disabled={sendingNotif}>
                    <Icon name="message" size={15} />{sendingNotif ? 'Sending…' : 'Send approved notification'}
                  </button>
                )}
                {stage === 'recovered' && notificationStatus === 'uncertain' && (
                  <p className="plan-disclaimer" style={{color: '#b45041'}}>
                    <Icon name="close" size={15} />Notification delivery outcome uncertain. Do not automatically redispatch.
                  </p>
                )}
                {stage === 'recovered' && notificationSent && (
                  <p className="plan-disclaimer" style={{color: '#2d9c8a'}}>
                    <Icon name="check" size={15} />Notification successfully dispatched (simulated provider).
                  </p>
                )}
                {stage === 'partial_failure' && <button className="primary-button primary-button--warning" onClick={resetDemo}><Icon name="refresh" size={17} />Review recovery again</button>}
                {(stage === 'proposed') && <button className="primary-button" onClick={() => approvePlan()} disabled={isBusy}><Icon name="shield" size={17} />Approve exact plan hash</button>}
                {(stage === 'approved') && <button className="primary-button" onClick={() => executeApprovedPlan()} disabled={isBusy}><Icon name="check" size={17} />Execute approved plan</button>}
                {(stage === 'approved') && <button className="secondary-button" onClick={() => executeApprovedPlan('reschedule_ride')} disabled={isBusy}><Icon name="terminal" size={15} />Execute failure path</button>}
                {stage === 'uncertain' && <button className="primary-button primary-button--warning" onClick={resetDemo}><Icon name="refresh" size={17} />Reset UI</button>}
                {stage === 'review' && <button className="secondary-button" style={{display:'none'}} onClick={() => executeApprovedPlan('reschedule_ride')}><Icon name="terminal" size={15} />Run failure path</button>}
                {(stage === 'recovered' || stage === 'partial_failure') && <button className="secondary-button" onClick={() => setRawCallsOpen(true)}><Icon name="audit" size={15} />View audit trail</button>}
              </div>
              <div className="plan-disclaimer"><Icon name="shield" size={14} />No bookings or messages are sent until you approve. Server cryptographic hash protects against tampering.</div>
            </section>
          </section>

          <aside className="activity-column">
            <div className="activity-header"><div><span className="eyebrow">AGENT ACTIVITY</span><h2>What’s happening</h2></div><span className="live-pill"><i />MIXED</span></div>
            <div className="activity-card panel">
              <div className="activity-card-head">
                <span className="activity-pulse"><i /><i /><i /></span>
                <div>
                  <strong>
                    {stage === 'review'
                      ? 'Waiting for your proposal'
                      : stage === 'proposed'
                        ? 'Plan proposed · Awaiting approval'
                        : stage === 'approved'
                          ? 'Plan approved · Ready to execute'
                          : stage === 'executing'
                            ? 'Executing approved plan'
                            : stage === 'recovered'
                              ? 'Backend confirmed recovery'
                              : stage === 'partial_failure'
                                ? 'Backend reported partial failure'
                                : 'Execution outcome unresolved'}
                  </strong>
                  <small>
                    {stage === 'review'
                      ? (liveTrip ? 'Itinerary and flight disruption loaded from backend.' : 'Timeline mixes illustrative scenario rows with live tool results.')
                      : stage === 'proposed'
                        ? 'Server hash generated. No actions have been executed.'
                        : stage === 'approved'
                          ? 'Approval hash locked on server. Ready for execution.'
                          : stage === 'executing'
                            ? 'Transaction running on backend with lease heartbeat…'
                            : backendResult
                              ? `Server status: ${backendResult.status}`
                              : 'Awaiting server confirmation.'}
                  </small>
                </div>
              </div>
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

      {preferencesOpen && <div className="drawer-backdrop" onClick={() => setPreferencesOpen(false)}><aside className="preferences-drawer" role="dialog" aria-modal="true" aria-labelledby="preferences-title" onClick={(event) => event.stopPropagation()}><div className="drawer-header"><div><span className="eyebrow">TRAVELLER MEMORY</span><h2 id="preferences-title">Preferences</h2></div><button className="icon-button icon-button--large" onClick={() => setPreferencesOpen(false)} aria-label="Close preferences"><Icon name="close" size={18} /></button></div><p className="drawer-intro">{preferencesDeleted ? 'No saved preferences are active. Restore defaults or make a new choice below.' : 'These choices shape how Trip Rescue ranks alternatives. You can edit or delete them at any time.'}</p><div className="preference-list"><PreferenceRow label="Preferred airline" value={preferences.airline} options={['SAS / Star Alliance', 'Any airline']} onChange={() => togglePreference('airline', ['SAS / Star Alliance', 'Any airline'])} /><PreferenceRow label="Seat preference" value={preferences.seat} options={['Window', 'Aisle']} onChange={() => togglePreference('seat', ['Window', 'Aisle'])} /><PreferenceRow label="Max cost change" value={preferences.maxDelta} options={['$75', '$150']} onChange={() => togglePreference('maxDelta', ['$75', '$150'])} /><PreferenceRow label="Overnight travel" value={preferences.overnight} options={['Avoid overnight flights', 'Overnight is okay']} onChange={() => togglePreference('overnight', ['Avoid overnight flights', 'Overnight is okay'])} /></div><div className="drawer-note"><Icon name="database" size={15} /><span>Edits call the backend save/delete tools. UI only updates after the server confirms. Providers remain simulated.</span></div><div className="drawer-actions"><button className="delete-link" onClick={deletePreferencesAction}>Delete saved preferences</button><button className="restore-link" onClick={restorePreferencesAction}>Restore defaults</button></div></aside></div>}
      {toast && <div className="toast" role="status"><span className="toast-icon"><Icon name="check" size={14} /></span>{toast}</div>}
    </div>
  )
}

function PreferenceRow({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: () => void }) {
  return <button className="preference-row" onClick={onChange}><span><span className="eyebrow">{label}</span><strong>{value}</strong></span><span className="preference-switch"><span className="preference-switch-dot" /><Icon name="chevron" size={14} /></span></button>
}

export default App
