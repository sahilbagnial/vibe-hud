import time
from vibe_hud.core.session_store import SessionStore


def test_new_session_created_on_first_event():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "SessionStart"})
    s = store.get("s1")
    assert s["status"] == "idle"
    assert s["repo_name"] == "foo"


def test_userpromptsubmit_sets_working_and_prompt():
    store = SessionStore()
    store.apply_event({
        "session_id": "s1", "cwd": "/repo/foo",
        "hook_event_name": "UserPromptSubmit", "prompt": "do the thing",
    })
    s = store.get("s1")
    assert s["status"] == "working"
    assert s["prompt"] == "do the thing"
    assert s["started_at"] is not None


def test_pretooluse_sets_tool_name_without_resetting_started_at():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "UserPromptSubmit", "prompt": "x"})
    first_started = store.get("s1")["started_at"]
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "PreToolUse", "tool_name": "Bash"})
    s = store.get("s1")
    assert s["tool_name"] == "Bash"
    assert s["started_at"] == first_started


def test_notification_sets_attention():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "Notification", "message": "Approve?"})
    s = store.get("s1")
    assert s["status"] == "attention"
    assert s["detail"] == "Approve?"


def test_stop_sets_complete_and_duration():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "UserPromptSubmit", "prompt": "x"})
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "Stop"})
    s = store.get("s1")
    assert s["status"] == "complete"
    assert s["completed_at"] is not None
    assert s["duration"] is not None


def test_explicit_status_overrides_event_name():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "status": "attention", "message": "custom"})
    s = store.get("s1")
    assert s["status"] == "attention"
    assert s["title"] == "custom"


def test_dismiss_removes_session():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "Stop"})
    store.dismiss("s1")
    assert store.get("s1") is None


def test_sweep_expired_removes_only_old_complete_sessions():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "Stop"})
    store.get("s1")["completed_at"] = int(time.time() * 1000) - 120_000
    store.apply_event({"session_id": "s2", "cwd": "/repo/bar", "hook_event_name": "UserPromptSubmit", "prompt": "x"})
    expired = store.sweep_expired(60)
    assert expired == ["s1"]
    assert store.get("s1") is None
    assert store.get("s2") is not None


def test_sweep_expired_noop_when_auto_dismiss_falsy():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/foo", "hook_event_name": "Stop"})
    assert store.sweep_expired(0) == []
    assert store.get("s1") is not None


def test_to_state_data_empty():
    store = SessionStore()
    data = store.to_state_data()
    assert data["aggregate_status"] == "idle"
    assert data["sessions"] == []


def test_to_state_data_prioritizes_attention_over_working():
    store = SessionStore()
    store.apply_event({"session_id": "working", "cwd": "/repo/a", "hook_event_name": "PreToolUse", "tool_name": "Bash"})
    store.apply_event({"session_id": "attn", "cwd": "/repo/b", "hook_event_name": "Notification", "message": "x"})
    data = store.to_state_data()
    assert data["aggregate_status"] == "attention"
    assert data["active_session_id"] == "attn"


def test_to_state_data_active_timer_for_working():
    store = SessionStore()
    store.apply_event({"session_id": "s1", "cwd": "/repo/a", "hook_event_name": "UserPromptSubmit", "prompt": "x"})
    store.get("s1")["started_at"] = int(time.time() * 1000) - 5000
    data = store.to_state_data()
    assert data["active_timer"] >= 5
