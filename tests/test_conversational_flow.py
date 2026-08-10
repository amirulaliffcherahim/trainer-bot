"""Tests for Planning v3 conversational flow, check-ins, slang, and micro-routines."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import db
import guardrails
import ingest_kb
import retrieval
import workouts
from bot import FAST_LOG_SYSTEM_PROMPT


def test_fast_log_prompt_has_checkin_and_concise_rules():
    assert "Reply in 1-3 short, punchy lines" in FAST_LOG_SYSTEM_PROMPT
    assert "follow-up check-in" in FAST_LOG_SYSTEM_PROMPT
    assert "cooldown" in FAST_LOG_SYSTEM_PROMPT or "tight" in FAST_LOG_SYSTEM_PROMPT


def test_guardrails_symptom_keywords_malaysian():
    for word in ["betis", "peha", "ketat", "lenguh", "sengal", "kaku", "koyak", "lemau"]:
        assert word in guardrails.SYMPTOM_KEYWORDS
        assert guardrails.has_symptom_signals(f"my {word} feels weird")


def test_get_tomorrow_schedule(tmp_path):
    conn = db.init_db(tmp_path / "test.db")
    today = date(2026, 8, 10)
    tomorrow_iso = "2026-08-11"

    # Unseeded
    preview = workouts.get_tomorrow_schedule(conn, today)
    assert "rest" in preview.lower()

    # Seed rest workout
    conn.execute(
        "INSERT INTO workout_plan (date, session_type, description) VALUES (?, 'rest', 'Full rest')",
        (tomorrow_iso,),
    )
    conn.commit()
    preview = workouts.get_tomorrow_schedule(conn, today)
    assert "rest day" in preview.lower()

    # Seed tempo run
    conn.execute(
        "UPDATE workout_plan SET session_type = 'tempo_run', prescribed_km = 8.0, target_pace = '6:30' WHERE date = ?",
        (tomorrow_iso,),
    )
    conn.commit()
    preview = workouts.get_tomorrow_schedule(conn, today)
    assert "tempo_run" in preview
    assert "8 km" in preview
    assert "@6:30" in preview
    conn.close()


def test_micro_rag_ingest_and_retrieval(tmp_path):
    conn = db.init_db(tmp_path / "test.db")
    embedder = retrieval.TfEmbedder()
    kb_root = Path("knowledge")

    count = ingest_kb.ingest_kb(conn, embedder, kb_root, clear=True)
    assert count > 0

    # Test retrieval for calf/betis tightness
    hits = retrieval.retrieve(conn, embedder, "mobility", "betis calf tightness after heat run", top_k=3, threshold=0.1)
    assert len(hits) > 0
    sources = [h.source.lower() for h in hits]
    assert any("tight_calf" in s or "cool_down" in s or "flush" in s for s in sources)
    conn.close()
