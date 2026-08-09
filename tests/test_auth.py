"""test_auth.py — allowlist gate, debounce, draft store, callback length,
application wiring (no network)."""

from db import init_db
from bot import Debouncer, DraftStore, authorize, build_application
from config import Settings
from strava import StravaFields, StravaRead, build_confirm_keyboard

ALLOWED = {123456789}


def _settings(**overrides) -> Settings:
    base = dict(
        telegram_bot_token="123:testtoken",
        deepseek_api_key="sk-test",
        allowed_user_ids=ALLOWED,
    )
    base.update(overrides)
    return Settings(**base)


def test_authorize_allows_only_allowlisted() -> None:
    assert authorize(123456789, ALLOWED)
    assert not authorize(999, ALLOWED)
    assert not authorize(None, ALLOWED)


def test_debouncer_one_per_second() -> None:
    debouncer = Debouncer(min_interval=1.0)
    now = 1000.0
    assert debouncer.allow(1, now=now)
    assert not debouncer.allow(1, now=now + 0.5)
    assert debouncer.allow(1, now=now + 1.1)  # interval passed
    assert debouncer.allow(2, now=now + 0.1)  # different user unaffected


def test_draft_store_roundtrip_and_ttl() -> None:
    store = DraftStore(ttl=0.05)
    read = StravaRead(fields=StravaFields(distance_km=5.0), ocr_text="x")
    draft_id = store.put(read)
    assert len(draft_id) < 20  # short — keeps callback_data way under 64 bytes
    assert store.get(draft_id) is read
    assert store.pop(draft_id) is read
    assert store.get(draft_id) is None


def test_draft_store_expires() -> None:
    store = DraftStore(ttl=0.01)
    read = StravaRead(fields=StravaFields(distance_km=5.0), ocr_text="x")
    draft_id = store.put(read)
    import time as _time

    _time.sleep(0.02)
    assert store.get(draft_id) is None


def test_draft_store_fix_state() -> None:
    store = DraftStore()
    read = StravaRead(fields=StravaFields(distance_km=5.0), ocr_text="x")
    draft_id = store.put(read)
    store.set_fix(1, draft_id, "distance_km")
    assert store.pop_fix(1) == (draft_id, "distance_km")
    assert store.pop_fix(1) is None


def test_callback_data_under_64_bytes() -> None:
    store = DraftStore()
    read = StravaRead(fields=StravaFields(distance_km=5.0), ocr_text="x")
    draft_id = store.put(read)
    keyboard = build_confirm_keyboard(draft_id)
    for row in keyboard.inline_keyboard:
        for button in row:
            assert button.callback_data is not None
            assert len(button.callback_data.encode("utf-8")) <= 64


def test_build_application_registers_handlers() -> None:
    conn = init_db(":memory:")
    app = build_application(_settings(db_path=":memory:"), auto_seed=False)
    names = [handler.callback.__name__ for handler in app.handlers[0]]
    for expected in (
        "cmd_start", "cmd_today", "cmd_summary", "cmd_log", "cmd_weight",
        "cmd_phase", "cmd_personas", "handle_text", "handle_photo",
        "handle_callback",
    ):
        assert expected in names, f"missing handler {expected}"
    assert app.job_queue is not None, "job-queue extra missing — notifications silently disabled"
    conn.close()


def test_auto_seed_ingests_kb_when_empty(tmp_path) -> None:
    from bot import auto_seed
    from retrieval import TfEmbedder

    conn = init_db(":memory:")
    kb_root = tmp_path / "runner"
    kb_root.mkdir()
    (kb_root / "pacing.md").write_text("# Pacing\n\nGoal pace from the target.")
    auto_seed(conn, kb_root=tmp_path, embedder=TfEmbedder())
    count = conn.execute("SELECT COUNT(*) AS n FROM kb_chunks").fetchone()["n"]
    assert count >= 1
    # Second call is a no-op.
    auto_seed(conn, kb_root=tmp_path, embedder=TfEmbedder())
    assert conn.execute("SELECT COUNT(*) AS n FROM kb_chunks").fetchone()["n"] == count
