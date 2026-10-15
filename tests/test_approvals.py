"""Safety tests for approval + execution (Phase 4)."""
from server.store.bootstrap import ensure_schema
from server.store.database import init_db
from server.store import repositories as repo
from server.tools import trip_tools
from server.domain import execution_service


def setup_function():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)


def test_execute_without_approval_rejected():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    result = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert result["ok"] is False
    assert result["error"] in ("NOT_APPROVED", "NO_VALID_APPROVAL")


def test_hash_mismatch_rejected():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    bad = trip_tools.approve_rescue_plan(plan["plan_id"], "wrong-hash-value")
    assert bad["ok"] is False
    assert bad["error"] == "HASH_MISMATCH"


def test_happy_path_approve_and_execute():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    approval = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    assert approval["ok"] is True
    result = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert result["ok"] is True
    assert result["status"] == "succeeded"
    assert len(result["steps"]) >= 3


def test_idempotent_reexecute():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    first = trip_tools.execute_rescue_plan(plan["plan_id"])
    second = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert first["status"] == "succeeded"
    assert second.get("idempotent") is True
    assert second["status"] == "succeeded"


def test_forced_failure_triggers_compensation():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    result = trip_tools.execute_rescue_plan(plan["plan_id"], force_fail_step="reschedule_ride")
    assert result["ok"] is False
    assert result["status"] in ("failed_rolled_back", "partially_failed")
    assert any(s.get("status") == "failed" for s in result["steps"])
    assert len(result.get("compensations", [])) >= 1


def test_stale_plan_version():
    """Approving then changing plan would require a new proposal; old hash fails."""
    plan1 = trip_tools.propose_rescue_plan("FLIGHT-A")
    plan2 = trip_tools.propose_rescue_plan("FLIGHT-B")  # new version
    # Try to approve plan1 with its own hash – still valid if still pending
    # But execute plan2 without approval should fail
    result = trip_tools.execute_rescue_plan(plan2["plan_id"])
    assert result["ok"] is False


def test_expired_approval_rejected():
    """Approval past expires_at must not authorize execution."""
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import execution_service

    execution_service.set_force_fail(None)
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    approval = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    assert approval["ok"] is True

    # Force expiry in DB
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with db_session() as conn:
        conn.execute(
            "UPDATE approvals SET expires_at = ? WHERE plan_id = ?",
            (past, plan["plan_id"]),
        )

    result = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert result["ok"] is False
    assert result["error"] in ("NO_VALID_APPROVAL", "NOT_APPROVED")


def test_atomic_claim_prevents_double_execute():
    """Second execute after first claims should be idempotent, not double-run."""
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    first = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert first.get("status") == "succeeded"
    second = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert second.get("idempotent") is True


def test_recover_stuck_executing():
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import execution_service

    plan = trip_tools.propose_rescue_plan("FLIGHT-B")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    with db_session() as conn:
        conn.execute(
            "UPDATE plans SET status = 'executing' WHERE id = ?",
            (plan["plan_id"],),
        )
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, 'w-stale')",
            (plan["plan_id"], (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()),
        )
    result = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
    assert result["ok"] is True
    assert result["status"] == "partially_failed"


def test_ownership_check_on_approve_rejected():
    """Approving a plan belonging to another user must be rejected."""
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    bad = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"], user_id="user-imposter")
    assert bad["ok"] is False
    assert bad["error"] == "OWNERSHIP"


def test_ownership_check_on_execute_rejected():
    """Executing a plan belonging to another user must be rejected."""
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    bad = trip_tools.execute_rescue_plan(plan["plan_id"], user_id="user-imposter")
    assert bad["ok"] is False
    assert bad["error"] == "OWNERSHIP"



def test_recover_missing_plan():
    from server.domain import execution_service
    r = execution_service.recover_stuck_execution("NO-SUCH-PLAN")
    assert r["ok"] is False
    assert r["error"] == "PLAN_NOT_FOUND"


def test_recover_wrong_owner():
    from server.store.database import db_session
    from server.domain import execution_service
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
    r = execution_service.recover_stuck_execution(plan["plan_id"], user_id="other-user")
    assert r["ok"] is False
    assert r["error"] == "OWNERSHIP"


def test_recover_marks_missing_steps_interrupted():
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import execution_service
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, 'w-stale')",
            (plan["plan_id"], (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()),
        )
    r = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
    assert r["ok"] is True
    assert r["status"] == "partially_failed"
    assert len(r.get("interrupted_steps") or []) >= 1
    statuses = {s["status"] for s in r["steps"]}
    assert "interrupted" in statuses
    # repeated recovery is idempotent
    r2 = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
    assert r2.get("idempotent") is True or r2["status"] == "partially_failed"


def test_recover_via_tool_surface():
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    plan = trip_tools.propose_rescue_plan("FLIGHT-B")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, 'w-stale')",
            (plan["plan_id"], (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()),
        )
    r = trip_tools.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
    assert r["ok"] is True
    assert r["status"] == "partially_failed"


def test_recover_refuses_active_lease():
    from server.store.database import db_session
    from server.domain import execution_service
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, datetime('now'), 'w1')",
            (plan["plan_id"],),
        )
    r = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=3600)
    assert r.get("error") == "EXECUTION_ACTIVE"
    assert r.get("status") == "executing"


def test_finalize_failed_when_reconcile_wins():
    """If send row is no longer 'sending', finalization must not report success."""
    from server.store.database import db_session
    from server.domain import notification_service
    from server.providers import message_provider

    message_provider.reset_send_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-B")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    trip_tools.execute_rescue_plan(plan["plan_id"])
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])

    # Pre-seed a sending row then mark uncertain (simulate reconcile race)
    with db_session() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO notification_sends
               (id, plan_id, draft_id, content_hash, result_json, status, created_at, claimed_at)
               VALUES ('race-1', ?, ?, ?, '[]', 'uncertain', datetime('now'), datetime('now'))""",
            (plan["plan_id"], draft["draft_id"], draft["content_hash"]),
        )
    # send should not succeed
    result = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert result.get("ok") is False


def test_genuinely_active_execution_cannot_be_recovered_prematurely():
    """An execution actively working and renewing lease cannot be recovered."""
    import threading
    from server.domain import execution_service

    execution_service.reset_execution_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    in_action = threading.Event()
    resume_action = threading.Event()

    def action_hook(step_num: int, action_type: str):
        if step_num == 2:
            in_action.set()
            resume_action.wait(timeout=5)

    execution_service.set_before_action_hook(action_hook)
    result_box = []

    def run_worker():
        res = trip_tools.execute_rescue_plan(plan["plan_id"])
        result_box.append(res)

    t = threading.Thread(target=run_worker)
    t.start()
    try:
        assert in_action.wait(timeout=5), "Worker did not reach step 2"
        # Try to recover with a 60-second lease
        rec = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
        assert rec["ok"] is False
        assert rec["error"] == "EXECUTION_ACTIVE"
    finally:
        resume_action.set()
        t.join(timeout=5)
        execution_service.reset_execution_hooks()

    assert len(result_box) == 1
    assert result_box[0]["ok"] is True
    assert result_box[0]["status"] == "succeeded"


def test_expired_execution_can_be_recovered():
    """An execution past its stale lease can be recovered."""
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import execution_service

    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        past = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, 'w-old')",
            (plan["plan_id"], past),
        )

    rec = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
    assert rec["ok"] is True
    assert rec["status"] == "partially_failed"


def test_two_recovery_attempts_cannot_both_claim_same_stale_execution():
    """Concurrent recovery attempts: exactly one claims, both are idempotent."""
    import threading
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import execution_service

    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        past = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, 'w-old')",
            (plan["plan_id"], past),
        )

    results = []
    def do_recover():
        r = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
        results.append(r)

    t1 = threading.Thread(target=do_recover)
    t2 = threading.Thread(target=do_recover)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert len(results) == 2
    assert all(r["ok"] is True for r in results)
    assert all(r["status"] == "partially_failed" for r in results)

    # Check database: no duplicate interrupted steps
    with db_session() as conn:
        rows = conn.execute(
            "SELECT step_number, COUNT(*) as cnt FROM execution_steps WHERE plan_id = ? GROUP BY step_number",
            (plan["plan_id"],),
        ).fetchall()
        for r in rows:
            assert r["cnt"] == 1


def test_worker_losing_ownership_cannot_overwrite_recovered_state():
    """A worker that loses its claim to recovery must fail closed with OWNERSHIP_LOST."""
    import threading
    from server.domain import execution_service
    from server.store.database import db_session

    execution_service.reset_execution_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    in_action = threading.Event()
    resume_action = threading.Event()

    def action_hook(step_num: int, action_type: str):
        if step_num == 2:
            in_action.set()
            resume_action.wait(timeout=5)

    execution_service.set_before_action_hook(action_hook)
    result_box = []

    def run_worker():
        res = trip_tools.execute_rescue_plan(plan["plan_id"])
        result_box.append(res)

    t = threading.Thread(target=run_worker)
    t.start()
    try:
        assert in_action.wait(timeout=5)
        # Concurrent recovery worker steals the claim via internal test helper
        rec = execution_service.force_recover_for_test(plan["plan_id"])
        assert rec["ok"] is True
        assert rec["status"] == "partially_failed"
    finally:
        resume_action.set()
        t.join(timeout=5)
        execution_service.reset_execution_hooks()

    assert len(result_box) == 1
    worker_res = result_box[0]
    assert worker_res["ok"] is False
    assert worker_res["error"] == "OWNERSHIP_LOST"

    # Crucial: the database plan status must remain partially_failed, NOT overwritten to succeeded!
    cur_plan = repo.get_plan(plan["plan_id"])
    assert cur_plan["status"] == "partially_failed"


def test_worker_losing_ownership_cannot_begin_additional_actions_or_compensations():
    """A worker cannot perform compensations after losing ownership."""
    import threading
    from server.domain import execution_service
    from server.store.database import db_session

    execution_service.reset_execution_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    in_comp = threading.Event()
    resume_comp = threading.Event()

    def comp_hook(prev_action: dict):
        in_comp.set()
        resume_comp.wait(timeout=5)

    execution_service.set_before_compensation_hook(comp_hook)
    result_box = []

    def run_worker():
        res = trip_tools.execute_rescue_plan(plan["plan_id"], force_fail_step="reschedule_ride")
        result_box.append(res)

    t = threading.Thread(target=run_worker)
    t.start()
    try:
        assert in_comp.wait(timeout=5)
        # Stolen by recovery worker during compensation via internal test helper
        rec = execution_service.force_recover_for_test(plan["plan_id"])
        assert rec["ok"] is True
    finally:
        resume_comp.set()
        t.join(timeout=5)
        execution_service.reset_execution_hooks()

    assert len(result_box) == 1
    assert result_box[0]["ok"] is False
    assert result_box[0]["error"] == "OWNERSHIP_LOST"


def test_missing_claim_or_timestamp_fails_closed_on_recovery():
    """Recovery without timestamp/claim info fails closed when stale_after_seconds > 0."""
    from server.store.database import db_session
    from server.domain import execution_service

    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        conn.execute("DELETE FROM execution_claims WHERE plan_id = ?", (plan["plan_id"],))
        conn.execute("DELETE FROM execution_steps WHERE plan_id = ?", (plan["plan_id"],))

    rec = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=60)
    assert rec["ok"] is False
    assert rec["error"] == "CANNOT_ESTABLISH_STALENESS"
    assert rec["status"] == "executing"

    # Plan is still executing, not prematurely ruined
    cur = repo.get_plan(plan["plan_id"])
    assert cur["status"] == "executing"


def test_notification_send_paused_in_provider_cannot_overwrite_reconciled_state():
    """Deterministic concurrency test: provider paused, reconciled to uncertain, cannot finalize success."""
    import threading
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import notification_service
    from server.providers import message_provider

    message_provider.reset_send_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    trip_tools.execute_rescue_plan(plan["plan_id"])
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])

    send_started = threading.Event()
    reconcile_done = threading.Event()

    def provider_hook():
        send_started.set()
        reconcile_done.wait(timeout=5)

    message_provider.set_before_send(provider_hook)
    result_box = []

    def run_send():
        res = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
        result_box.append(res)

    t = threading.Thread(target=run_send)
    t.start()
    try:
        assert send_started.wait(timeout=5), "send_notifications did not reach provider hook"
        # The send reservation is now 'sending' in DB. Age the reservation to make it stale:
        past = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        with db_session() as conn:
            conn.execute(
                "UPDATE notification_sends SET claimed_at = ? WHERE plan_id = ?",
                (past, plan["plan_id"]),
            )
        # Reconcile while the provider is paused via internal test helper
        rec = notification_service.force_reconcile_for_test(
            plan["plan_id"], draft["content_hash"]
        )
        assert rec["ok"] is True
        assert rec["status"] == "uncertain"
    finally:
        reconcile_done.set()
        t.join(timeout=5)
        message_provider.reset_send_hooks()

    assert len(result_box) == 1
    send_res = result_box[0]
    # Finalization must fail because the status was changed to uncertain!
    assert send_res["ok"] is False
    assert send_res["error"] == "SEND_UNCERTAIN"
    assert send_res["status"] == "uncertain"

    # DB status must remain uncertain, NOT overwritten to sent
    with db_session() as conn:
        row = conn.execute(
            "SELECT status FROM notification_sends WHERE plan_id = ?", (plan["plan_id"],)
        ).fetchone()
        assert row["status"] == "uncertain"

    # Further send attempts must not re-dispatch provider
    before_count = message_provider.get_send_count()
    retry_res = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert retry_res["ok"] is False
    assert retry_res["error"] == "SEND_UNCERTAIN"
    assert message_provider.get_send_count() == before_count


def test_active_execution_cannot_be_interrupted_by_zero_negative_or_short_threshold():
    """Active execution within lease cannot be interrupted or have its claim removed by zero, negative, or short threshold."""
    from datetime import datetime, timezone
    from server.store.database import db_session
    from server.domain import execution_service
    from fastapi.testclient import TestClient
    from server.http_facade import app

    client = TestClient(app)
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    now_iso = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute("UPDATE plans SET status = 'executing' WHERE id = ?", (plan["plan_id"],))
        conn.execute(
            "INSERT OR REPLACE INTO execution_claims (plan_id, claimed_at, worker_id) VALUES (?, ?, 'worker-active-1')",
            (plan["plan_id"], now_iso),
        )

    # 1. Negative threshold
    r_neg_dom = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=-10)
    assert r_neg_dom["ok"] is False
    assert r_neg_dom["error"] == "INVALID_ARGUMENT"

    r_neg_http = client.post("/tools/recover_stuck_execution", json={"plan_id": plan["plan_id"], "stale_after_seconds": -10})
    assert r_neg_http.status_code == 422

    # 2. Zero threshold (cannot force recovery of active execution)
    r_zero_dom = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=0)
    assert r_zero_dom["ok"] is False
    assert r_zero_dom["error"] == "INVALID_ARGUMENT"

    r_zero_http = client.post("/tools/recover_stuck_execution", json={"plan_id": plan["plan_id"], "stale_after_seconds": 0})
    assert r_zero_http.status_code == 422

    # 3. Unreasonably short threshold (e.g. 5s < 30s)
    r_short_dom = execution_service.recover_stuck_execution(plan["plan_id"], stale_after_seconds=5)
    assert r_short_dom["ok"] is False
    assert r_short_dom["error"] == "INVALID_ARGUMENT"

    r_short_tool = trip_tools.recover_stuck_execution(plan["plan_id"], stale_after_seconds=5)
    assert r_short_tool["ok"] is False
    assert r_short_tool["error"] == "INVALID_ARGUMENT"

    r_short_http = client.post("/tools/recover_stuck_execution", json={"plan_id": plan["plan_id"], "stale_after_seconds": 5})
    assert r_short_http.status_code == 422

    # Verify active execution is NOT interrupted and claim was NOT removed
    cur_plan = repo.get_plan(plan["plan_id"])
    assert cur_plan["status"] == "executing"
    with db_session() as conn:
        claim = conn.execute("SELECT worker_id FROM execution_claims WHERE plan_id = ?", (plan["plan_id"],)).fetchone()
        assert claim is not None
        assert claim["worker_id"] == "worker-active-1"


def test_active_notification_send_renews_lease_and_prevents_premature_reconciliation():
    """Genuinely active send renews lease continuously and cannot be prematurely reconciled."""
    import threading
    import time
    from server.store.database import db_session
    from server.domain import notification_service
    from server.providers import message_provider

    message_provider.reset_send_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    trip_tools.execute_rescue_plan(plan["plan_id"])
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])

    send_started = threading.Event()
    allow_finish = threading.Event()

    def slow_provider_hook():
        send_started.set()
        allow_finish.wait(timeout=5)

    message_provider.set_before_send(slow_provider_hook)
    result_box = []

    def run_worker():
        res = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
        result_box.append(res)

    t = threading.Thread(target=run_worker)
    t.start()
    try:
        assert send_started.wait(timeout=5)
        # Give heartbeat time to tick and refresh claimed_at
        time.sleep(0.7)
        # Attempt to reconcile with server lease threshold (30s)
        rec = notification_service.reconcile_stale_notification_send(
            plan["plan_id"], draft["content_hash"], stale_after_seconds=30
        )
        # Must refuse reconciliation because the heartbeat has kept claimed_at fresh!
        assert rec["ok"] is False
        assert rec["error"] == "SEND_IN_PROGRESS"
        assert rec["status"] == "sending"
    finally:
        allow_finish.set()
        t.join(timeout=5)
        message_provider.reset_send_hooks()

    assert len(result_box) == 1
    assert result_box[0]["ok"] is True
    assert result_box[0]["status"] == "sent"

    # Status in database must be sent
    with db_session() as conn:
        row = conn.execute(
            "SELECT status FROM notification_sends WHERE plan_id = ?", (plan["plan_id"],)
        ).fetchone()
        assert row["status"] == "sent"


def test_genuinely_stale_reservation_becomes_uncertain_without_redispatch():
    """Genuinely stale reservation is marked uncertain and neither reconcile nor subsequent send redispatches provider."""
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.domain import notification_service
    from server.providers import message_provider

    message_provider.reset_send_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    trip_tools.execute_rescue_plan(plan["plan_id"])
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])

    # Create an abandoned/stale reservation with claimed_at 300 seconds ago
    past_iso = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    send_id = "send-stale-test"
    with db_session() as conn:
        conn.execute(
            """INSERT INTO notification_sends
               (id, plan_id, draft_id, content_hash, result_json, status, created_at, claimed_at)
               VALUES (?, ?, ?, ?, '[]', 'sending', ?, ?)""",
            (send_id, plan["plan_id"], draft["draft_id"], draft["content_hash"], past_iso, past_iso),
        )
        conn.execute(
            "UPDATE notification_drafts SET status = 'sending' WHERE id = ?",
            (draft["draft_id"],),
        )

    before_count = message_provider.get_send_count()

    # Reconcile genuinely stale reservation
    rec = notification_service.reconcile_stale_notification_send(
        plan["plan_id"], draft["content_hash"], stale_after_seconds=60
    )
    assert rec["ok"] is True
    assert rec["status"] == "uncertain"

    # Provider must NOT have been called during reconciliation
    assert message_provider.get_send_count() == before_count

    # DB state must be uncertain
    with db_session() as conn:
        s_row = conn.execute("SELECT status FROM notification_sends WHERE id = ?", (send_id,)).fetchone()
        assert s_row["status"] == "uncertain"
        d_row = conn.execute("SELECT status FROM notification_drafts WHERE id = ?", (draft["draft_id"],)).fetchone()
        assert d_row["status"] == "uncertain"

    # Subsequent send attempt must NOT retry or redispatch provider
    retry = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert retry["ok"] is False
    assert retry["error"] == "SEND_UNCERTAIN"
    assert message_provider.get_send_count() == before_count


def test_two_concurrent_execution_requests_dispatch_provider_steps_once():
    """Two concurrent execute requests: exactly one claims and runs steps; no duplicated side effects."""
    import threading
    import time
    from server.store.database import db_session

    execution_service.reset_execution_hooks()
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])

    start_gate = threading.Event()
    results = []
    lock = threading.Lock()

    def run_worker():
        start_gate.wait(timeout=5)
        res = trip_tools.execute_rescue_plan(plan["plan_id"])
        with lock:
            results.append(res)

    t1 = threading.Thread(target=run_worker)
    t2 = threading.Thread(target=run_worker)
    t1.start()
    t2.start()

    # Release both threads at once to compete on the claim
    start_gate.set()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(results) == 2
    # Exactly one executed full plan; the other is either idempotent or claim failed
    successes = [r for r in results if r.get("status") == "succeeded" and not r.get("idempotent")]
    assert len(successes) == 1

    # Verify database: each step number exists exactly once
    with db_session() as conn:
        rows = conn.execute(
            "SELECT step_number, COUNT(*) as cnt FROM execution_steps WHERE plan_id = ? GROUP BY step_number",
            (plan["plan_id"],),
        ).fetchall()
        assert len(rows) >= 3
        for r in rows:
            assert r["cnt"] == 1

        p_row = conn.execute("SELECT status FROM plans WHERE id = ?", (plan["plan_id"],)).fetchone()
        assert p_row["status"] == "succeeded"
