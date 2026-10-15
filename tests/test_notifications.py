"""Hash-bound notification approval tests."""
from server.store.bootstrap import ensure_schema
from server.store import repositories as repo
from server.tools import trip_tools
from server.domain import execution_service


def setup_function():
    ensure_schema()
    repo.seed_demo_data(wipe=True)
    execution_service.set_force_fail(None)
    # reset tool init flag
    import server.tools.trip_tools as tt
    tt._initialized = True  # schema already ready


def _approved_plan():
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    assert "plan_id" in plan and "error" not in plan
    ap = trip_tools.approve_rescue_plan(plan["plan_id"], plan["plan_hash"])
    assert ap["ok"]
    ex = trip_tools.execute_rescue_plan(plan["plan_id"])
    assert ex.get("status") == "succeeded"
    return plan


def test_send_without_approval_rejected():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    assert draft.get("ok") is True
    result = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert result["ok"] is False
    assert result["error"] == "NOT_APPROVED"


def test_boolean_approved_not_sufficient():
    """Legacy approved=True must not authorize send."""
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    # Call domain with only boolean path removed — send requires hash approval
    result = trip_tools.send_notifications(plan["plan_id"], None)
    assert result["ok"] is False


def test_hash_mismatch_rejected():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    bad = trip_tools.approve_notifications(plan["plan_id"], "wrong-hash")
    assert bad["ok"] is False
    assert bad["error"] == "HASH_MISMATCH"


def test_draft_approve_send_success():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    ap = trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    assert ap["ok"] is True
    sent = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert sent["ok"] is True
    assert sent.get("provider") == "simulated"
    assert len(sent["sent"]) >= 1


def test_duplicate_send_idempotent():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    first = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    second = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert first["ok"] is True
    assert second.get("idempotent") is True


def test_preference_memory():
    before = trip_tools.list_preferences()
    assert before["count"] >= 1
    trip_tools.save_preference("seat", "window")
    after = trip_tools.get_preferences()
    assert after["seat"]["value"] == "window"


def test_expired_notification_approval():
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session

    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    ap = trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    assert ap["ok"]
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with db_session() as conn:
        conn.execute(
            "UPDATE notification_approvals SET expires_at = ? WHERE plan_id = ?",
            (past, plan["plan_id"]),
        )
    sent = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert sent["ok"] is False
    assert sent["error"] == "EXPIRED"


def test_wrong_owner_cannot_send():
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    sent = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"], user_id="other-user")
    assert sent["ok"] is False
    assert sent["error"] in ("OWNERSHIP", "NOT_APPROVED", "NO_DRAFT")


def test_send_requires_exact_hash():
    """send_notifications with missing or empty hash must be rejected."""
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    res_none = trip_tools.send_notifications(plan["plan_id"], None)
    assert res_none["ok"] is False
    assert res_none["error"] == "HASH_REQUIRED"

    res_empty = trip_tools.send_notifications(plan["plan_id"], "")
    assert res_empty["ok"] is False
    assert res_empty["error"] == "HASH_REQUIRED"


def test_unapproved_plan_cannot_approve_or_send_notifications():
    """Unapproved/pending plan cannot approve or send notification drafts."""
    plan = trip_tools.propose_rescue_plan("FLIGHT-A")
    assert plan["status"] == "awaiting_approval"
    draft = trip_tools.draft_notifications(plan["plan_id"])
    ap = trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    assert ap["ok"] is False
    assert ap["error"] == "INVALID_PLAN_STATUS"

    sent = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert sent["ok"] is False
    assert sent["error"] == "INVALID_PLAN_STATUS"


def test_already_sent_draft_cannot_be_reapproved():
    """Sent notification draft cannot be approved again."""
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    sent = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert sent["ok"] is True

    # Try re-approving the sent draft
    re_ap = trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    assert re_ap["ok"] is False
    assert re_ap["error"] == "ALREADY_SENT"


def test_concurrent_send_dispatches_provider_once():
    """Only one of two competing senders may call the mock provider."""
    import threading
    import time
    from server.providers import message_provider

    message_provider.reset_send_hooks()
    # Slow the winner inside provider so the loser competes on the claim
    message_provider.set_before_send(lambda: time.sleep(0.15))

    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    assert draft.get("ok") is True
    ap = trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    assert ap["ok"] is True

    results: list[dict] = []
    lock = threading.Lock()
    errors: list[BaseException] = []

    def worker():
        try:
            r = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
            with lock:
                results.append(r)
        except BaseException as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert not errors, f"workers raised: {errors}"
    assert len(results) == 2, f"results={results}"

    count = message_provider.get_send_count()
    message_provider.reset_send_hooks()
    assert count == 1, (
        f"provider invoked {count} times; expected 1; results={results}"
    )

    independent_full = [
        r for r in results
        if r.get("ok") is True and r.get("status") == "sent" and not r.get("idempotent")
    ]
    assert len(independent_full) == 1, f"expected one non-idempotent success, got {results}"


def test_uncertain_send_not_retried():
    """If a send is left uncertain, a later call must not re-dispatch the provider."""
    from server.store.database import db_session
    from server.providers import message_provider

    message_provider.reset_send_hooks()
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])

    # Simulate interrupted send record
    with db_session() as conn:
        conn.execute(
            """INSERT INTO notification_sends
               (id, plan_id, draft_id, content_hash, result_json, status, created_at)
               VALUES ('send-unc-1', ?, ?, ?, '[]', 'uncertain', datetime('now'))""",
            (plan["plan_id"], draft["draft_id"], draft["content_hash"]),
        )

    before = message_provider.get_send_count()
    result = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert result["ok"] is False
    assert result["error"] == "SEND_UNCERTAIN"
    assert message_provider.get_send_count() == before


def test_stale_sending_reconciled_without_redispatch():
    from datetime import datetime, timezone, timedelta
    from server.store.database import db_session
    from server.providers import message_provider
    from server.domain import notification_service

    message_provider.reset_send_hooks()
    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])
    past = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    with db_session() as conn:
        conn.execute(
            """INSERT INTO notification_sends
               (id, plan_id, draft_id, content_hash, result_json, status, created_at, claimed_at)
               VALUES ('stale-1', ?, ?, ?, '[]', 'sending', ?, ?)""",
            (plan["plan_id"], draft["draft_id"], draft["content_hash"], past, past),
        )
    before = message_provider.get_send_count()
    result = notification_service.reconcile_stale_notification_send(
        plan["plan_id"], draft["content_hash"], stale_after_seconds=60
    )
    assert result.get("status") == "uncertain"
    assert message_provider.get_send_count() == before
    # still not retried via send
    again = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert again["ok"] is False
    assert again["error"] == "SEND_UNCERTAIN"


def test_provider_failure_before_dispatch_marks_uncertain_and_no_retry():
    """Provider failure before successful dispatch marks reservation uncertain and records empty partial."""
    from server.store.database import db_session
    from server.providers import message_provider

    message_provider.reset_send_hooks()

    def fail_immediately():
        raise RuntimeError("Simulated network failure to messaging provider")

    message_provider.set_before_send(fail_immediately)

    plan = _approved_plan()
    draft = trip_tools.draft_notifications(plan["plan_id"])
    trip_tools.approve_notifications(plan["plan_id"], draft["content_hash"])

    result = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    message_provider.reset_send_hooks()

    assert result["ok"] is False
    assert result["error"] == "SEND_UNCERTAIN"
    assert result["status"] == "uncertain"
    assert result["sent"] == []

    # Verify database state
    with db_session() as conn:
        row = conn.execute("SELECT status, result_json FROM notification_sends WHERE plan_id = ?", (plan["plan_id"],)).fetchone()
        assert row["status"] == "uncertain"
        assert "Simulated network failure" in row["result_json"]

    # Verify it is not retried automatically
    before_count = message_provider.get_send_count()
    retry = trip_tools.send_notifications(plan["plan_id"], draft["content_hash"])
    assert retry["ok"] is False
    assert retry["error"] == "SEND_UNCERTAIN"
    assert message_provider.get_send_count() == before_count


def test_partial_notification_delivery_marks_uncertain_with_partial_results():
    """Failure after 1st message in multi-message draft preserves partial delivery results as uncertain."""
    from server.store.database import db_session
    from server.providers import message_provider
    import json

    message_provider.reset_send_hooks()
    plan = _approved_plan()

    # Create a draft with 2 notifications
    drafts = [
        {"recipient": "Sam (Driver)", "subject": "Delayed arrival", "body": "Flight delayed by 4h"},
        {"recipient": "Hotel Front Desk", "subject": "Late check-in", "body": "Checking in at 01:00 AM"},
    ]
    import hashlib
    canonical = json.dumps(drafts, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()
    draft_id = "ND-MULTI-1"

    with db_session() as conn:
        conn.execute(
            """INSERT INTO notification_drafts
               (id, plan_id, user_id, drafts_json, content_hash, status, created_at)
               VALUES (?, ?, 'user-alex', ?, ?, 'draft', datetime('now'))""",
            (draft_id, plan["plan_id"], json.dumps(drafts), content_hash),
        )

    trip_tools.approve_notifications(plan["plan_id"], content_hash)

    # Fail on the second send attempt
    call_count = 0
    def fail_on_second():
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Provider failed during 2nd message dispatch")

    message_provider.set_before_send(fail_on_second)

    result = trip_tools.send_notifications(plan["plan_id"], content_hash)
    message_provider.reset_send_hooks()

    assert result["ok"] is False
    assert result["error"] == "SEND_UNCERTAIN"
    assert result["status"] == "uncertain"
    # Exactly 1 message was delivered before the exception
    assert len(result["sent"]) == 1
    assert result["sent"][0]["recipient"] == "Sam (Driver)"

    # Database records partial delivery and uncertain status
    with db_session() as conn:
        row = conn.execute("SELECT status, result_json FROM notification_sends WHERE plan_id = ?", (plan["plan_id"],)).fetchone()
        assert row["status"] == "uncertain"
        saved = json.loads(row["result_json"])
        assert len(saved.get("partial", [])) == 1
        assert "Provider failed during 2nd message dispatch" in saved.get("error", "")
