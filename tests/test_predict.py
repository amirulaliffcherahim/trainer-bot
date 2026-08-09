"""predict.py tests — Riegel math, anchor selection, refit, bands, proposal."""

import math

import pytest

from db import init_db
from predict import (
    DEFAULT_EXPONENT,
    HALF_MARATHON_KM,
    Prediction,
    best_anchor,
    format_prediction,
    format_seconds,
    predict,
    refit_exponent,
    riegel,
    target_proposal,
)


def _anchor(distance_km, time_sec, source="verified_effort", verified=1):
    return {
        "distance_km": distance_km,
        "time_sec": time_sec,
        "source": source,
        "verified": verified,
    }


def test_riegel_formula_exact() -> None:
    # 10 km in 70:00 (4200s) → half marathon at exponent 1.06
    t2 = riegel(4200.0, 10.0, HALF_MARATHON_KM, DEFAULT_EXPONENT)
    expected = 4200.0 * (HALF_MARATHON_KM / 10.0) ** 1.06
    assert t2 == pytest.approx(expected, rel=1e-9)


def test_refit_exponent_two_anchors() -> None:
    a1 = _anchor(5.0, 1500.0)
    a2 = _anchor(10.0, 3300.0)
    b = refit_exponent([a1, a2])
    expected = math.log(3300.0 / 1500.0) / math.log(10.0 / 5.0)
    assert b == pytest.approx(expected)
    assert 1.0 <= b <= 1.15


def test_refit_single_anchor_defaults() -> None:
    assert refit_exponent([_anchor(5.0, 1500.0)]) == DEFAULT_EXPONENT


def test_refit_clamped_to_sane_range() -> None:
    # Degenerate pair would produce b >> 1.15
    b = refit_exponent([_anchor(5.0, 1500.0), _anchor(10.0, 3050.0)])
    assert b <= 1.15
    b2 = refit_exponent([_anchor(5.0, 1500.0), _anchor(10.0, 2900.0)])
    assert b2 >= 1.0


def test_best_anchor_prefers_race() -> None:
    anchors = [
        _anchor(10.0, 4200.0, "verified_effort"),
        _anchor(21.0975, 9000.0, "race"),
        _anchor(5.0, 2000.0, "verified_effort"),
    ]
    assert best_anchor(anchors)["source"] == "race"


def test_best_anchor_fastest_within_pool() -> None:
    anchors = [_anchor(10.0, 4200.0), _anchor(5.0, 1900.0)]  # 5k avg 6.33 m/km > 10k 7.0
    assert best_anchor(anchors)["distance_km"] == 5.0


def test_predict_none_without_anchors() -> None:
    conn = init_db(":memory:")
    assert predict(conn) is None


def test_predict_band_and_exponent() -> None:
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO performance_anchors (date, distance_km, time_sec, source, verified) "
        "VALUES ('2026-07-01', 10.0, 4200.0, 'race', 1)"
    )
    conn.commit()
    p = predict(conn)
    assert p is not None
    assert p.low_sec == pytest.approx(p.predicted_sec * 0.95)
    assert p.high_sec == pytest.approx(p.predicted_sec * 1.05)
    assert p.exponent == DEFAULT_EXPONENT
    assert p.anchor_source == "race"


def test_predict_ignores_unverified_and_out_of_range() -> None:
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO performance_anchors (date, distance_km, time_sec, source, verified) "
        "VALUES ('2026-07-01', 10.0, 4200.0, 'verified_effort', 0)"
    )
    conn.execute(
        "INSERT INTO performance_anchors (date, distance_km, time_sec, source, verified) "
        "VALUES ('2026-07-01', 5.0, 60.0, 'race', 1)"  # 1 min — outside Riegel range
    )
    conn.commit()
    assert predict(conn) is None


def test_format_seconds() -> None:
    assert format_seconds(149.8 * 60) == "2:29:48"  # 8988 s
    assert format_seconds(418.0) == "6:58"
    assert format_seconds(0) == "0:00"


def test_format_prediction_contains_band() -> None:
    p = Prediction(21.0975, 8988.0, 8538.6, 9437.4, 1.06, "race")
    text = format_prediction(p)
    assert "2:29:48" in text
    assert "2:22:19" in text  # low band
    assert "±5%" in text


def test_target_proposal_fires_on_material_delta() -> None:
    p = Prediction(21.0975, 8400.0, 7980.0, 8820.0, 1.06, "race")
    proposal = target_proposal(p, current_target_sec=8988.0)  # 2:29:48 target
    assert proposal is not None
    assert "faster than" in proposal
    assert "Update the target" in proposal


def test_target_proposal_silent_within_threshold() -> None:
    p = Prediction(21.0975, 9000.0, 8550.0, 9450.0, 1.06, "race")
    assert target_proposal(p, current_target_sec=8988.0) is None
