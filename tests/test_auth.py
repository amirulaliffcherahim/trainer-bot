"""bot.py tests — allowlist gate, debounce, draft store, callback length,
application wiring, /target parsing (no network)."""

import pytest

from bot import (
    Debouncer,
    DraftStore,
    authorize,
    build_application,
    parse_target_arg,
    resolve_log_date,
)
from db import init_db
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
    app = build_application(_settings(db_path=":memory:"), auto_seed_kb=False)
    names = [handler.callback.__name__ for handler in app.handlers[0]]
    for expected in (
        "cmd_start", "cmd_today", "cmd_summary", "cmd_log", "cmd_weight",
        "cmd_phase", "cmd_personas", "cmd_target", "handle_text",
        "handle_photo", "handle_callback",
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


def test_build_application_auto_seed_runs_without_crash(monkeypatch) -> None:
    """Regression: the auto_seed parameter name must not shadow the
    auto_seed() function (TypeError: 'bool' object is not callable)."""
    import bot as bot_module
    from retrieval import TfEmbedder

    monkeypatch.setattr(bot_module, "_get_embedder", lambda: TfEmbedder())
    app = build_application(_settings(db_path=":memory:"))  # auto_seed_kb=True
    conn = app.bot_data["conn"]
    count = conn.execute("SELECT COUNT(*) AS n FROM kb_chunks").fetchone()["n"]
    assert count >= 1


# --- /target parsing + date resolution -------------------------------------


def test_parse_target_arg() -> None:
    name, sec = parse_target_arg("SELMAR Half Marathon 2:30:00")
    assert name == "SELMAR Half Marathon"
    assert sec == 9000
    name, sec = parse_target_arg("10K 55:00")
    assert name == "10K"
    assert sec == 3300
    name, sec = parse_target_arg("5K 32:45")
    assert sec == 1965
    with pytest.raises(ValueError):
        parse_target_arg("no time here")
    with pytest.raises(ValueError):
        parse_target_arg("race 2:99:00")
    with pytest.raises(ValueError):
        parse_target_arg("race 3:00:99")


def test_resolve_log_date() -> None:
    from datetime import date

    today = date(2026, 7, 15)
    assert resolve_log_date("2026-07-28", today) == "2026-07-28"
    assert resolve_log_date("yesterday", today) == "2026-07-14"
    assert resolve_log_date("today", today) == "2026-07-15"
    assert resolve_log_date("3 days ago", today) == "2026-07-12"
    assert resolve_log_date("last saturday", today) == "2026-07-11"  # 2026-07-15 is a Wednesday
    assert resolve_log_date(None, today) is None
    assert resolve_log_date("not a date", today) is None


# --- /profile parsing + snapshot -------------------------------------------


def test_parse_profile_arg() -> None:
    from bot import parse_profile_arg

    updates = parse_profile_arg(["height=175", "age=28", "vo2=n/a"])
    assert updates == {"height_cm": 175.0, "age": 28, "vo2_max": None}
    updates = parse_profile_arg(["weight=56.5", "max_bpm=190", "resting_bpm=-"])
    assert updates == {"weight_kg": 56.5, "max_bpm": 190, "resting_bpm": None}
    with pytest.raises(ValueError):
        parse_profile_arg(["shoe_size=42"])
    with pytest.raises(ValueError):
        parse_profile_arg(["age=250"])
    with pytest.raises(ValueError):
        parse_profile_arg(["age=abc"])


def test_profile_snapshot_formats_na() -> None:
    from bot import profile_snapshot

    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO athlete_profile (user_id, height_cm, weight_kg, age, vo2_max, "
        "max_bpm, resting_bpm, target_race, target_pace) "
        "VALUES (1, 175, 55.0, 28, NULL, 190, 55, 'SELMAR Half Marathon', '7:06 min/km')"
    )
    conn.commit()
    snapshot = profile_snapshot(conn, 1)
    assert "175 cm" in snapshot
    assert "VO2 max n/a" in snapshot
    assert "190 bpm" in snapshot
    assert "SELMAR Half Marathon" in snapshot
    assert "No profile data" in profile_snapshot(conn, 99)


def test_profile_columns_exist_after_migration() -> None:
    conn = init_db(":memory:")
    columns = {
        r["name"]
        for r in conn.execute("PRAGMA table_info(athlete_profile)")
    }
    for expected in ("age", "vo2_max", "max_bpm", "resting_bpm"):
        assert expected in columns
