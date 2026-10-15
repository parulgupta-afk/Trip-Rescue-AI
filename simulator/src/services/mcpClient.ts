const rawBase = (import.meta as any).env?.VITE_MCP_URL || 'http://localhost:8000'
const BASE = String(rawBase).replace(/\/+$/, '')

export async function callTool(name: string, args: Record<string, unknown> = {}): Promise<any> {
  const res = await fetch(`${BASE}/tools/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = data?.detail?.message || data?.message || data?.error || `${name}: ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  if (data && data.ok === false && data.error) {
    throw new Error(data.message || data.error)
  }
  if (data && data.error && !data.plan_id && !data.alternatives && !data.id) {
    throw new Error(data.error)
  }
  return data
}

export const mcp = {
  getTrip: () => callTool('get_trip'),
  checkFlightStatus: () => callTool('check_flight_status'),
  getPreferences: () => callTool('get_preferences'),
  listPreferences: () => callTool('list_preferences'),
  searchAlternatives: () => callTool('search_alternatives'),
  proposeRescuePlan: (id: string) => callTool('propose_rescue_plan', { selected_flight_id: id }),
  savePreference: (key: string, value: unknown) => callTool('save_preference', { key, value }),
  deletePreference: (key: string) => callTool('delete_preference', { key }),
  approveRescuePlan: (planId: string, planHash: string) =>
    callTool('approve_rescue_plan', { plan_id: planId, plan_hash: planHash }),
  executeRescuePlan: (planId: string, forceFailStep?: string) =>
    callTool('execute_rescue_plan', {
      plan_id: planId,
      ...(forceFailStep ? { force_fail_step: forceFailStep } : {}),
    }),
  getPlanStatus: (planId: string) => callTool('get_plan_status', { plan_id: planId }),
  draftNotifications: (planId: string) => callTool('draft_notifications', { plan_id: planId }),
  approveNotifications: (planId: string, draftHash: string) =>
    callTool('approve_notifications', { plan_id: planId, draft_hash: draftHash }),
  sendNotifications: (planId: string, draftHash: string) =>
    callTool('send_notifications', { plan_id: planId, draft_hash: draftHash }),
  recoverStuckExecution: (planId: string, staleAfterSeconds?: number) =>
    callTool('recover_stuck_execution', {
      plan_id: planId,
      ...(staleAfterSeconds ? { stale_after_seconds: staleAfterSeconds } : {}),
    }),
  reconcileStaleNotificationSend: (planId: string, contentHash: string, staleAfterSeconds?: number) =>
    callTool('reconcile_stale_notification_send', {
      plan_id: planId,
      content_hash: contentHash,
      ...(staleAfterSeconds ? { stale_after_seconds: staleAfterSeconds } : {}),
    }),
}
