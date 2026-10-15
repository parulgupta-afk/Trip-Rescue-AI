PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT DEFAULT 'UTC',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(id),
    flight_number TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    airline TEXT,
    seat TEXT
);

CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(id),
    kind TEXT NOT NULL,  -- hotel | ride
    provider_reference TEXT,
    details_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed'
);

CREATE TABLE IF NOT EXISTS preferences (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'explicit',  -- explicit | confirmed | default
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, key)
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    version INTEGER NOT NULL DEFAULT 1,
    actions_json TEXT NOT NULL,
    total_cost_delta INTEGER NOT NULL DEFAULT 0,
    plan_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | executing | succeeded | failed_rolled_back | partially_failed | cancelled
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    plan_hash TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    expires_at TEXT,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS execution_steps (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    step_number INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,  -- sending | sent | uncertain  -- pending | success | failed | compensated
    result_json TEXT,
    error_code TEXT,
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    plan_id TEXT,
    tool_name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_drafts (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    user_id TEXT NOT NULL,
    drafts_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_approvals (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    draft_id TEXT NOT NULL REFERENCES notification_drafts(id),
    content_hash TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    expires_at TEXT,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS notification_sends (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    draft_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    status TEXT NOT NULL,  -- sending | sent | uncertain
    created_at TEXT NOT NULL,
    claimed_at TEXT,
    UNIQUE(plan_id, content_hash)
);


CREATE TABLE IF NOT EXISTS execution_claims (
    plan_id TEXT PRIMARY KEY,
    claimed_at TEXT NOT NULL,
    worker_id TEXT
);
