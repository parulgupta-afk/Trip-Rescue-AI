import { useState, useCallback } from 'react'
import { mcp, ToolCall } from './services/mcpClient'

type Stage = 'idle' | 'disruption' | 'alternatives' | 'plan' | 'executing' | 'done'

export default function App() {
  const [stage, setStage] = useState<Stage>('idle')
  const [logs, setLogs] = useState<ToolCall[]>([])
  const [status, setStatus] = useState<any>(null)
  const [alternatives, setAlternatives] = useState<any[]>([])
  const [plan, setPlan] = useState<any>(null)
  const [execResult, setExecResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const log = useCallback((entry: ToolCall) => {
    setLogs(prev => [...prev, entry])
  }, [])

  const runTool = useCallback(async (name: string, fn: () => Promise<any>) => {
    const start = Date.now()
    const ts = new Date().toISOString().slice(11, 19)
    log({ name, status: 'pending', timestamp: ts })
    try {
      const result = await fn()
      log({ name, status: 'success', durationMs: Date.now() - start, result, timestamp: ts })
      return result
    } catch (e: any) {
      log({ name, status: 'error', durationMs: Date.now() - start, error: e.message, timestamp: ts })
      throw e
    }
  }, [log])

  const handleFixTrip = async () => {
    setLoading(true); setError(null); setLogs([]); setExecResult(null)
    try {
      await runTool('get_trip', () => mcp.getTrip())
      const st = await runTool('check_flight_status', () => mcp.checkFlightStatus())
      setStatus(st)
      await runTool('get_preferences', () => mcp.getPreferences())
      setStage('disruption')
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleSearch = async () => {
    setLoading(true); setError(null)
    try {
      const res = await runTool('search_alternatives', () => mcp.searchAlternatives())
      setAlternatives(res.alternatives || [])
      setStage('alternatives')
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleSelect = async (flightId: string) => {
    setLoading(true); setError(null)
    try {
      const p = await runTool('propose_rescue_plan', () => mcp.proposeRescuePlan(flightId))
      setPlan(p)
      setStage('plan')
    } catch (e: any) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleApproveAndExecute = async (forceFail?: string) => {
    if (!plan?.plan_id || !plan?.plan_hash) return
    setLoading(true); setError(null); setStage('executing')
    try {
      const approval = await runTool('approve_rescue_plan', () =>
        mcp.approveRescuePlan(plan.plan_id, plan.plan_hash)
      )
      if (!approval.ok) {
        setError(approval.message || approval.error || 'Approval failed')
        setStage('plan')
        return
      }
      const result = await runTool('execute_rescue_plan', () =>
        mcp.executeRescuePlan(plan.plan_id, forceFail)
      )
      setExecResult(result)
      setStage('done')
    } catch (e: any) {
      setError(e.message)
      setStage('plan')
    } finally { setLoading(false) }
  }

  const handleReset = () => {
    setStage('idle'); setStatus(null); setAlternatives([]); setPlan(null)
    setExecResult(null); setLogs([]); setError(null)
  }

  return (
    <>
      <header>
        <h1>🚀 Trip Rescue AI</h1>
        <p>One request. One coordinated recovery. You’re always in control.</p>
      </header>

      <div className="layout">
        <main>
          {stage === 'idle' && (
            <div className="card">
              <h2>Ready</h2>
              <p style={{ margin: '0.75rem 0' }}>
                Simulate a 4-hour flight delay for traveller <strong>Alex</strong> (DEL → JFK).
              </p>
              <button className="btn-primary" disabled={loading} onClick={handleFixTrip}>
                {loading ? 'Working…' : 'My flight is delayed. Fix my trip.'}
              </button>
            </div>
          )}

          {stage === 'disruption' && status && (
            <div className="card">
              <h2>⚠️ Trip Alert</h2>
              <p style={{ margin: '0.5rem 0' }}>{status.message}</p>
              <p><strong>Delay:</strong> {status.delay_hours} hours</p>
              <h3 style={{ marginTop: '1rem' }}>Potential impact</h3>
              <ul style={{ paddingLeft: '1.25rem', margin: '0.5rem 0' }}>
                {status.affected?.map((a: any, i: number) => (
                  <li key={i}>{a.type}: {a.reason} ({a.risk})</li>
                ))}
              </ul>
              <button className="btn-primary" style={{ marginTop: '1rem' }} onClick={handleSearch} disabled={loading}>
                Review alternative flights
              </button>
            </div>
          )}

          {stage === 'alternatives' && (
            <div className="card">
              <h2>Ranked Alternatives</h2>
              {alternatives.map((alt) => (
                <div key={alt.id} style={{ borderBottom: '1px solid #e2e8f0', padding: '0.75rem 0' }}>
                  <strong>#{alt.rank} {alt.flight_number}</strong> ({alt.airline}) — +₹{alt.extra_cost}
                  <div style={{ fontSize: '0.9rem', color: '#475569' }}>{alt.why}</div>
                  <div style={{ fontSize: '0.85rem' }}>Dep {alt.departure} → Arr {alt.arrival}</div>
                  <button className="btn-primary" style={{ marginTop: '0.5rem' }}
                    onClick={() => handleSelect(alt.id)} disabled={loading}>
                    Select {alt.id}
                  </button>
                </div>
              ))}
            </div>
          )}

          {(stage === 'plan' || stage === 'executing') && plan && (
            <div className="card">
              <h2>Rescue Plan {plan.plan_id}</h2>
              <p className="status-pending">Status: Awaiting approval (hash-bound)</p>
              <p><strong>Total cost change:</strong> +₹{plan.total_cost_delta}</p>
              <p style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                Plan hash: {plan.plan_hash?.slice(0, 32)}…
              </p>
              <h3 style={{ marginTop: '1rem' }}>Actions</h3>
              <ul style={{ paddingLeft: '1.25rem' }}>
                {plan.actions?.map((a: any, i: number) => (
                  <li key={i}>{a.type} → {a.target || a.recipient || a.flight_number}</li>
                ))}
              </ul>
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem', flexWrap: 'wrap' }}>
                <button className="btn-primary" disabled={loading} onClick={() => handleApproveAndExecute()}>
                  {loading ? 'Working…' : 'Approve Plan'}
                </button>
                <button className="btn-secondary" disabled={loading}
                  onClick={() => handleApproveAndExecute('reschedule_ride')}>
                  Approve + Force Ride Failure
                </button>
                <button className="btn-secondary" disabled={loading} onClick={handleReset}>
                  Cancel
                </button>
              </div>
              <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: '#64748b' }}>
                Server verifies the exact plan hash before execution. A forced failure demonstrates compensation.
              </p>
            </div>
          )}

          {stage === 'done' && execResult && (
            <div className="card">
              <h2>
                {execResult.status === 'succeeded' ? '✅ Recovery Complete' : '⚠️ Partial / Rolled Back'}
              </h2>
              <p>
                Status: <strong className={execResult.status === 'succeeded' ? 'status-success' : 'status-error'}>
                  {execResult.status}
                </strong>
              </p>
              <p style={{ margin: '0.5rem 0' }}>{execResult.message}</p>
              <h3 style={{ marginTop: '1rem' }}>Execution steps</h3>
              <ul style={{ paddingLeft: '1.25rem' }}>
                {execResult.steps?.map((s: any, i: number) => (
                  <li key={i}>
                    Step {s.step}: {s.type} → <span className={s.status === 'success' ? 'status-success' : 'status-error'}>{s.status}</span>
                    {s.message && ` — ${s.message}`}
                  </li>
                ))}
              </ul>
              {execResult.compensations?.length > 0 && (
                <>
                  <h3 style={{ marginTop: '1rem' }}>Compensations</h3>
                  <ul style={{ paddingLeft: '1.25rem' }}>
                    {execResult.compensations.map((c: any, i: number) => (
                      <li key={i}>{c.type || c.message} → {c.status}</li>
                    ))}
                  </ul>
                </>
              )}
              <button className="btn-primary" style={{ marginTop: '1.25rem' }} onClick={handleReset}>
                Start over
              </button>
            </div>
          )}

          {error && (
            <div className="card" style={{ borderLeft: '4px solid #dc2626' }}>
              <strong className="status-error">Error</strong>
              <p>{error}</p>
            </div>
          )}
        </main>

        <aside>
          <div className="card">
            <h3>Tool Execution Log</h3>
            <div className="tool-log">
              {logs.length === 0 && <span style={{ opacity: 0.6 }}>No calls yet</span>}
              {logs.map((l, i) => (
                <div key={i} style={{ marginBottom: '0.4rem' }}>
                  <span style={{ color: '#94a3b8' }}>[{l.timestamp}]</span>{' '}
                  <span style={{
                    color: l.status === 'success' ? '#34d399' : l.status === 'error' ? '#f87171' : '#fbbf24'
                  }}>{l.name}</span>{' '}
                  {l.status === 'success' && <span>✓ {l.durationMs}ms</span>}
                  {l.status === 'error' && <span>✗ {l.error}</span>}
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </>
  )
}
