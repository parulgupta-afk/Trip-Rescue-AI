const BASE = import.meta.env.VITE_MCP_URL || 'http://localhost:8000'

export async function callTool(name: string, args: Record<string, unknown> = {}): Promise<any> {
  const res = await fetch(`${BASE}/tools/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!res.ok) throw new Error(`${name}: ${res.status}`)
  return res.json()
}

export const mcp = {
  getTrip: () => callTool('get_trip'),
  checkFlightStatus: () => callTool('check_flight_status'),
  getPreferences: () => callTool('get_preferences'),
  searchAlternatives: () => callTool('search_alternatives'),
  proposeRescuePlan: (id: string) => callTool('propose_rescue_plan', { selected_flight_id: id }),
  approveRescuePlan: (planId: string, planHash: string) =>
    callTool('approve_rescue_plan', { plan_id: planId, plan_hash: planHash }),
  executeRescuePlan: (planId: string, forceFailStep?: string) =>
    callTool('execute_rescue_plan', {
      plan_id: planId,
      ...(forceFailStep ? { force_fail_step: forceFailStep } : {}),
    }),
  draftNotifications: (planId: string) => callTool('draft_notifications', { plan_id: planId }),
  sendNotifications: (planId: string) => callTool('send_notifications', { plan_id: planId, approved: true }),
  savePreference: (key: string, value: unknown) => callTool('save_preference', { key, value }),
  listPreferences: () => callTool('list_preferences'),
}
