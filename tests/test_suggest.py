"""test_suggest.py — 10 triggers + anti-nag caps + challenges roundtrip."""

from datetime import datetime

from challenges import (
    accept_challenge,
    mark_completed,
    pick_template,
    skip_challenge,
    week_challenges,
)
from db import init_db
from suggest import (
    DismissalDedup,
    MuteState,
    PushBudget,
    evaluate_suggestions,
    in_quiet_hours,
    trigger_form_check,
    trigger_injury_watch,
    trigger_milestone,
    trigger_phase_boundary,
    trigger_plan_drift,
    trigger_prediction_update,
    trigger_recovery_nudge,
    trigger_session_adjustment,
    trigger_silence_check,
    trigger_weekly_challenge,
)

NOW = datetime(2026, 7, 15, 14, 0)  # afternoon — before-noon cap not in play


def test_quiet_hours_boundaries() -> None:
    assert in_quiet_hours(datetime(2026, 7, 15, 23, 0))
    assert in_quiet_hours(datetime(2026, 7, 15, 6, 0))
    assert not in_quiet_hours(datetime(2026, 7, 15, 7, 0))
    assert not in_quiet_hours(datetime(2026, 7, 15, 13, 0))


def test_push_budget_two_per_day() -> None:
    budget = PushBudget()
    assert budget.can_push(datetime(2026, 7, 15, 10, 0))
    budget.record(datetime(2026, 7, 15, 10, 0))
    assert budget.can_push(datetime(2026, 7, 15, 13, 0))  # afternoon — noon cap free
    budget.record(datetime(2026, 7, 15, 13, 0))
    assert not budget.can_push(datetime(2026, 7, 15, 14, 0))


def test_push_budget_one_before_noon() -> None:
    budget = PushBudget()
    budget.record(datetime(2026, 7, 15, 9, 0))
    assert not budget.can_push(datetime(2026, 7, 15, 10, 30))
    assert budget.can_push(datetime(2026, 7, 15, 12, 0))  # afternoon frees the slot


def test_push_budget_resets_daily() -> None:
    budget = PushBudget()
    budget.record(datetime(2026, 7, 15, 10, 0))
    budget.record(datetime(2026, 7, 15, 11, 0))
    assert budget.can_push(datetime(2026, 7, 16, 10, 0))  # next day


def test_mute_state() -> None:
    import time as _time

    state = MuteState()
    state.mute(1, 0.05)
    assert state.muted(1)
    _time.sleep(0.06)
    assert not state.muted(1)


def test_dismissal_dedup_blocks_seven_days() -> None:
    import time as _time

    dedup = DismissalDedup(ttl=0.05)
    dedup.dismiss(1, "recovery_nudge")
    assert dedup.blocked(1, "recovery_nudge")
    _time.sleep(0.06)
    assert not dedup.blocked(1, "recovery_nudge")
    assert not dedup.blocked(1, "milestone")


# --- triggers -------------------------------------------------------------


def test_weekly_challenge_trigger() -> None:
    conn = init_db(":memory:")
    suggestion = trigger_weekly_challenge(conn, "2026-07-13", "base")
    assert suggestion is not None
    assert suggestion.type == "weekly_challenge"
    assert suggestion.action == "Accept challenge"


def test_prediction_update_trigger_thresholds() -> None:
    assert trigger_prediction_update(6, 4.0) is not None
    assert trigger_prediction_update(5, 4.0) is None  # too few efforts
    assert trigger_prediction_update(6, 2.0) is None  # trend too small


def test_recovery_nudge_trend_and_rpe() -> None:
    assert trigger_recovery_nudge([6.0, 5.0, 4.0], True) is not None  # up 2 weeks
    assert trigger_recovery_nudge([7.5, 5.0, 5.0], True) is not None  # high + quality today
    assert trigger_recovery_nudge([5.0, 5.0, 5.0], False) is None


def test_injury_watch_trigger() -> None:
    assert trigger_injury_watch({"quad": 3, "shin": 1}) is not None
    assert "quad" in trigger_injury_watch({"quad": 3}).message
    assert trigger_injury_watch({"quad": 1, "shin": 1}) is None


def test_session_adjustment_trigger() -> None:
    assert trigger_session_adjustment(temp_c=33.0) is not None
    assert trigger_session_adjustment(temp_c=28.0) is None
    assert trigger_session_adjustment(rain=True) is not None


def test_milestone_trigger() -> None:
    assert trigger_milestone(52.0, 3) is not None
    assert trigger_milestone(40.0, 14) is not None  # streak PR
    assert trigger_milestone(40.0, 3) is None


def test_plan_drift_trigger() -> None:
    assert trigger_plan_drift(3, 0.0) is not None
    assert trigger_plan_drift(0, 12.0) is not None
    assert trigger_plan_drift(1, 0.0) is None


def test_phase_boundary_trigger() -> None:
    assert trigger_phase_boundary(5) is not None
    assert trigger_phase_boundary(0) is not None
    assert trigger_phase_boundary(8) is None
    assert trigger_phase_boundary(-1) is None


def test_silence_check_trigger() -> None:
    assert trigger_silence_check(4) is not None
    assert trigger_silence_check(2) is None


def test_form_check_trigger() -> None:
    assert trigger_form_check(13, None) is not None  # quarterly
    assert trigger_form_check(1, 1) is not None  # post-injury return
    assert trigger_form_check(5, None) is None


# --- orchestrator caps ----------------------------------------------------


def _three_triggers():
    return [
        trigger_silence_check(4),
        trigger_plan_drift(3, 0.0),
        trigger_milestone(52.0, 3),
    ]


def test_evaluate_caps_at_two() -> None:
    pushes = evaluate_suggestions(triggers=_three_triggers(), now=NOW)
    assert len(pushes) == 2


def test_evaluate_quiet_hours_block_all() -> None:
    pushes = evaluate_suggestions(
        triggers=_three_triggers(), now=datetime(2026, 7, 15, 23, 0)
    )
    assert pushes == []


def test_evaluate_muted_block_all() -> None:
    pushes = evaluate_suggestions(triggers=_three_triggers(), now=NOW, muted=True)
    assert pushes == []


def test_evaluate_taper_silence() -> None:
    pushes = evaluate_suggestions(
        triggers=_three_triggers(), now=NOW, phase_name="taper_1"
    )
    assert pushes == []  # all three types banned in taper
    mixed = [
        trigger_phase_boundary(5),
        trigger_silence_check(4),
        trigger_milestone(52.0, 3),
    ]
    pushes = evaluate_suggestions(triggers=mixed, now=NOW, phase_name="taper_1")
    assert [p.type for p in pushes] == ["phase_boundary"]


def test_evaluate_dismissed_types_skipped() -> None:
    pushes = evaluate_suggestions(
        triggers=_three_triggers(), now=NOW, dismissed_types={"silence_check"}
    )
    assert all(p.type != "silence_check" for p in pushes)


def test_evaluate_budget_stops_mid_batch() -> None:
    budget = PushBudget()
    pushes = evaluate_suggestions(triggers=_three_triggers(), now=NOW, budget=budget)
    assert len(pushes) == 2
    assert not budget.can_push(NOW)  # budget consumed


# --- challenges ------------------------------------------------------------


def test_pick_template_deterministic_and_phase_filtered() -> None:
    conn = init_db(":memory:")
    a = pick_template(conn, "2026-07-13", "base")
    b = pick_template(conn, "2026-07-13", "base")
    assert a == b
    taper_pool = pick_template(conn, "2026-10-12", "taper")
    assert taper_pool is None or taper_pool.phase in ("any", "taper")


def test_accept_skip_complete_roundtrip() -> None:
    conn = init_db(":memory:")
    template = pick_template(conn, "2026-07-13", "base")
    challenge_id = accept_challenge(conn, "2026-07-13", template)
    mark_completed(conn, challenge_id)
    rows = week_challenges(conn, "2026-07-13")
    assert len(rows) == 1
    assert rows[0]["accepted"] == 1
    assert rows[0]["completed"] == 1


def test_skip_prevents_repeat_in_week() -> None:
    conn = init_db(":memory:")
    first = pick_template(conn, "2026-07-13", "base")
    skip_challenge(conn, "2026-07-13", first.title)
    second = pick_template(conn, "2026-07-13", "base")
    assert second is None or second.title != first.title
