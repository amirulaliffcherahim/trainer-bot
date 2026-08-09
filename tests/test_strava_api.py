"""strava_api tests — token refresh, activity mapping, sync + dedup
(injected fake HTTP, no network)."""

from strava_api import (
    StravaClient,
    StravaError,
    map_activity,
    sync_activities,
)
from db import init_db


class FakeHTTP:
    def __init__(self, token_payload, activities, fail_once_401=False):
        self.token_payload = token_payload
        self.activities = activities
        self.fail_once_401 = fail_once_401
        self.token_calls = 0
        self.get_calls = 0

    def post(self, url, **kwargs):
        self.token_calls += 1
        from strava_api import FakeHTTPResponse

        return FakeHTTPResponse(200, self.token_payload)

    def get(self, url, **kwargs):
        self.get_calls += 1
        from strava_api import FakeHTTPResponse

        if self.fail_once_401 and self.get_calls == 1:
            return FakeHTTPResponse(401, {})
        return FakeHTTPResponse(200, self.activities)


def _client(http, conn=None):
    return StravaClient("cid", "csecret", "rt0", conn=conn, http=http)


def test_token_refresh_and_rotation_persisted() -> None:
    conn = init_db(":memory:")
    http = FakeHTTP(
        {"access_token": "at1", "expires_at": 9999999999, "refresh_token": "rt1"},
        [],
    )
    client = _client(http, conn)
    assert client.refresh_access_token() == "at1"
    # Rotated refresh token persisted in kv_store.
    row = conn.execute("SELECT value FROM kv_store WHERE key='strava_refresh_token'").fetchone()
    assert row["value"] == "rt1"
    # A NEW client instance picks up the rotated token (survives restarts).
    http2 = FakeHTTP(
        {"access_token": "at2", "expires_at": 9999999999, "refresh_token": "rt2"},
        [],
    )
    client2 = _client(http2, conn)
    client2.refresh_access_token()
    assert http2.token_calls == 1  # used the persisted rt1


def test_token_refresh_failure_raises() -> None:
    class BadHTTP:
        def post(self, url, **kwargs):
            from strava_api import FakeHTTPResponse

            return FakeHTTPResponse(401, {})

    client = _client(BadHTTP())
    try:
        client.refresh_access_token()
        assert False, "should have raised"
    except StravaError:
        pass


def test_map_activity_computes_pace_in_code() -> None:
    activity = {
        "id": 42,
        "type": "Run",
        "name": "Saturday Long Run",
        "distance": 10000.0,  # 10 km
        "moving_time": 3600,  # 1 h
        "average_speed": 2.777,
        "start_date_local": "2026-07-11T06:30:00Z",
    }
    fields = map_activity(activity)
    assert fields["date"] == "2026-07-11"
    assert fields["session_type"] == "run"
    assert fields["distance_km"] == 10.0
    assert fields["moving_time_min"] == 60.0
    assert fields["avg_pace_sec_km"] == 360  # 3600*1000/10000 — computed
    assert fields["notes"] == "Saturday Long Run"


def test_sync_imports_runs_and_dedups() -> None:
    conn = init_db(":memory:")
    activities = [
        {"id": 1, "type": "Run", "name": "Easy", "distance": 5000.0,
         "moving_time": 1500, "start_date_local": "2026-07-10T06:00:00Z"},
        {"id": 2, "type": "Run", "name": "Long", "distance": 10000.0,
         "moving_time": 4200, "start_date_local": "2026-07-11T06:00:00Z"},
        {"id": 3, "type": "Ride", "name": "Bike", "distance": 20000.0,
         "moving_time": 3600, "start_date_local": "2026-07-11T08:00:00Z"},  # not a run
    ]
    client = _client(FakeHTTP({"access_token": "at", "expires_at": 9999999999}, activities))
    result = sync_activities(conn, client, user_id=1, now_epoch=1_800_000_000)
    assert result == {"added": 2, "skipped": 1}  # ride skipped

    rows = conn.execute("SELECT * FROM daily_logs ORDER BY id").fetchall()
    assert len(rows) == 2
    assert all(r["verified"] == 1 for r in rows)
    assert rows[0]["avg_pace_sec_km"] == 300  # 1500*1000/5000
    anchors = conn.execute("SELECT COUNT(*) AS n FROM performance_anchors").fetchone()["n"]
    assert anchors == 2

    # Second sync: everything already imported.
    result = sync_activities(conn, client, user_id=1, now_epoch=1_800_000_100)
    assert result == {"added": 0, "skipped": 3}
    assert conn.execute("SELECT COUNT(*) AS n FROM daily_logs").fetchone()["n"] == 2


def test_sync_retries_once_on_401() -> None:
    conn = init_db(":memory:")
    activities = [
        {"id": 9, "type": "Run", "name": "Tempo", "distance": 8000.0,
         "moving_time": 2880, "start_date_local": "2026-07-12T06:00:00Z"}
    ]
    http = FakeHTTP(
        {"access_token": "at", "expires_at": 9999999999, "refresh_token": "rt"},
        activities,
        fail_once_401=True,
    )
    client = _client(http, conn)
    result = sync_activities(conn, client, user_id=1, now_epoch=1_800_000_000)
    assert result["added"] == 1
    assert http.get_calls == 2  # 401 → refresh → retry
