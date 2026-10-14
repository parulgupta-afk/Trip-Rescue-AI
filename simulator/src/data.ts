export type DemoStage = 'review' | 'executing' | 'recovered' | 'partial_failure'
export type ToolTier = 'read' | 'propose' | 'commit'

export type Alternative = {
  id: string
  airline: string
  code: string
  flight: string
  route: string
  departure: string
  arrival: string
  duration: string
  stops: string
  seat: string
  price: string
  delta: number
  fit: string
  tags: string[]
  accent: string
}

export type ToolEvent = {
  id: string
  time: string
  tier: ToolTier
  name: string
  detail: string
}

/** All provider results in this demo are SIMULATED local mocks — not real airline/hotel APIs. */
export const PROVIDER_MODE = "SIMULATED" as const

export const trip = {
  code: 'TRP-00419',
  date: '18–22 JUN 2025',
  origin: 'Newark',
  originCode: 'EWR',
  destination: 'Stockholm',
  destinationCode: 'ARN',
  originalFlight: 'SK 908',
  originalTime: '18:10',
  revisedTime: '19:50',
  terminal: 'C · Gate 74',
  connection: 'Copenhagen',
  hotel: 'At Six Stockholm',
  ride: 'Arlanda → Norrmalm',
}

export const alternatives: Alternative[] = [
  {
    id: 'sas',
    airline: 'SAS',
    code: 'SK',
    flight: 'SK 910',
    route: 'EWR → CPH → ARN',
    departure: '20:25',
    arrival: '10:45',
    duration: '12h 20m',
    stops: '1 stop · 1h 15m layover',
    seat: '18A · window',
    price: '$842',
    delta: 27,
    fit: 'Best fit for your saved airline + window seat preferences.',
    tags: ['SAVED AIRLINE', 'WINDOW SEAT'],
    accent: '#f6b73c',
  },
  {
    id: 'lufthansa',
    airline: 'Lufthansa',
    code: 'LH',
    flight: 'LH 405',
    route: 'EWR → FRA → ARN',
    departure: '21:10',
    arrival: '11:25',
    duration: '11h 15m',
    stops: '1 stop · 1h 45m layover',
    seat: '14C · aisle',
    price: '$798',
    delta: -17,
    fit: 'Lowest total cost, but trades away your preferred airline.',
    tags: ['LOWEST COST'],
    accent: '#3f5bf6',
  },
  {
    id: 'finnair',
    airline: 'Finnair',
    code: 'AY',
    flight: 'AY 16',
    route: 'JFK → HEL → ARN',
    departure: '19:40',
    arrival: '12:10',
    duration: '13h 30m',
    stops: '1 stop · 2h 05m layover',
    seat: '22A · window',
    price: '$916',
    delta: 101,
    fit: 'Keeps a window seat, but departs JFK and exceeds your saved trip budget.',
    tags: ['WINDOW SEAT', 'JFK DEPARTURE', 'OVER BUDGET'],
    accent: '#2d9c8a',
  },
]

export const initialPreferences = {
  airline: 'SAS / Star Alliance',
  seat: 'Window',
  maxDelta: '$75',
  overnight: 'Avoid overnight flights',
  notifications: 'Draft messages, never send without approval',
}

export const toolEvents: ToolEvent[] = [
  { id: 'status', time: '14:32:08', tier: 'read', name: 'get_disruption', detail: 'SK 908 delay confirmed · 1h 40m' },
  { id: 'impact', time: '14:32:09', tier: 'read', name: 'get_trip_impact', detail: '3 downstream items at risk' },
  { id: 'rank', time: '14:32:11', tier: 'propose', name: 'rank_alternatives', detail: '3 replacement flights scored' },
  { id: 'plan', time: '14:32:13', tier: 'propose', name: 'build_rescue_plan', detail: 'Plan v3 · hash 8d2f…a91c' },
  { id: 'approval', time: 'waiting', tier: 'commit', name: 'approval_gate', detail: 'Explicit traveller approval required' },
]

export const rawCalls = [
  'read.get_disruption({ trip_id: "TRP-00419" })',
  'read.get_trip_impact({ flight: "SK 908", at: "2025-06-18T14:32:08Z" })',
  'propose.rank_alternatives({ preferences_hash: "pref_7ce2" })',
  'propose.build_rescue_plan({ alternative_id: "sas", version: 3 })',
  'commit.execute_plan({ approval_hash: "8d2f…a91c" }) // blocked until approval',
]
