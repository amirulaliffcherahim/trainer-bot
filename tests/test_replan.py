"""replan.py tests — data-driven proposals, never auto-applied."""

from predict import Prediction
from replan import (
    build_replan_report,
    pace_proposal,
    prediction_proposal,
    volume_proposal,
    weight_proposal,
)

TARGET_PACE = 426  # 7:06/km


def test_pace_proposal_faster_triggers_update() -> None:
    proposal = pace_proposal(410.0, TARGET_PACE)  # 16 s/km faster
    assert proposal is not None
    assert proposal.action == "/target"
    assert "faster than" in proposal.detail
    assert "6:50" in proposal.detail  # suggested new target


def test_pace_proposal_slower_flags_gap() -> None:
    proposal = pace_proposal(445.0, TARGET_PACE)
    assert proposal is not None
    assert "slower than" in proposal.detail


def test_pace_proposal_within_tolerance_silent() -> None:
    assert pace_proposal(420.0, TARGET_PACE) is None  # 6 s/km off
    assert pace_proposal(None, TARGET_PACE) is None


def test_volume_proposal_over_cap() -> None:
    proposal = volume_proposal(22.0, 18.5)  # +18.9%
    assert proposal is not None
    assert "10%" in proposal.detail
    assert volume_proposal(19.5, 18.5) is None  # +5.4%
    assert volume_proposal(5.0, 0.0) is None  # no baseline


def test_weight_proposal_losing_trend() -> None:
    proposal = weight_proposal(-0.8)
    assert proposal is not None
    assert "surplus" in proposal.detail
    assert weight_proposal(0.3) is None
    assert weight_proposal(None) is None


def test_prediction_proposal_uses_gap() -> None:
    prediction = Prediction(21.0975, 8400.0, 7980.0, 8820.0, 1.06, "race")
    proposal = prediction_proposal(prediction, target_sec=8988.0)
    assert proposal is not None
    assert proposal.action == "/predict"
    close = Prediction(21.0975, 9000.0, 8550.0, 9450.0, 1.06, "race")
    assert prediction_proposal(close, target_sec=8988.0) is None
    assert prediction_proposal(None, 8988.0) is None


def test_build_report_aggregates_and_empty_when_clean() -> None:
    assert (
        build_replan_report(
            pace_avg_sec_km=420.0,
            target_pace_sec_km=TARGET_PACE,
            this_week_km=19.5,
            prev_week_km=18.5,
            weight_trend_kg=0.3,
        )
        == []
    )
    report = build_replan_report(
        pace_avg_sec_km=410.0,
        target_pace_sec_km=TARGET_PACE,
        this_week_km=22.0,
        prev_week_km=18.5,
        weight_trend_kg=-0.8,
        prediction=Prediction(21.0975, 8400.0, 7980.0, 8820.0, 1.06, "race"),
        target_sec=8988.0,
    )
    titles = {p.title for p in report}
    assert titles == {"Pace improvement", "Volume spike", "Weight trend", "Prediction gap"}
