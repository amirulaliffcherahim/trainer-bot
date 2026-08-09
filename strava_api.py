"""Direct Strava API sync — authoritative numbers, no OCR.

OAuth2 flow: the app holds client_id/client_secret + a long-lived refresh
token (one-time setup via strava_auth.py). Access tokens expire after ~6h
and refresh tokens ROTATE on every refresh — the newest refresh token is
persisted in kv_store so the bot survives restarts.

Rules:
- Numbers come straight from Strava (distance in meters, moving time in
  seconds, speed in m/s). Pace is COMPUTED in code — never read, never
  rounded by a model.
- Only runs are imported; dedup by Strava activity id; every import is
  verified=1 and becomes a prediction anchor.
"""

from __future__ import annotations

import time

import httpx

from db import save_log

TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
TOKEN_EXPIRY_MARGIN = 60  # refresh 60s before expiry


class StravaError(RuntimeError):
    """Strava API failure (auth, network, rate limit)."""


class FakeHTTPResponse:
    """Minimal response stand-in (tests inject this)."""

    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=self  # type: ignore[arg-type]
            )


class StravaClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        *,
        conn=None,
        http=None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._conn = conn
        self._http = http or httpx.Client(timeout=30)
        self.access_token: str | None = None
        self.expires_at: float = 0.0

    # -- refresh token persistence (Strava rotates it) ----------------------

    def _persisted_refresh_token(self) -> str:
        if self._conn is None:
            return self.refresh_token
        row = self._conn.execute(
            "SELECT value FROM kv_store WHERE key = 'strava_refresh_token'"
        ).fetchone()
        return row["value"] if row else self.refresh_token

    def _persist_refresh_token(self, token: str) -> None:
        if self._conn is None:
            return
        self._conn.execute(
            "INSERT INTO kv_store (key, value) VALUES ('strava_refresh_token', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (token,),
        )
        self._conn.commit()

    # -- auth ---------------------------------------------------------------

    def refresh_access_token(self) -> str:
        self.refresh_token = self._persisted_refresh_token()
        response = self._http.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
        )
        if response.status_code >= 400:
            raise StravaError(
                f"Strava token refresh failed (HTTP {response.status_code}) — "
                "re-run strava_auth.py"
            )
        data = response.json()
        self.access_token = data["access_token"]
        self.expires_at = float(data.get("expires_at", 0))
        if data.get("refresh_token"):
            self._persist_refresh_token(data["refresh_token"])
        return self.access_token

    def _ensure_token(self) -> None:
        if self.access_token is None or time.time() >= self.expires_at - TOKEN_EXPIRY_MARGIN:
            self.refresh_access_token()

    # -- activities ---------------------------------------------------------

    def get_activities(self, after_epoch: int | None = None, per_page: int = 100) -> list[dict]:
        self._ensure_token()
        params: dict = {"per_page": per_page}
        if after_epoch:
            params["after"] = int(after_epoch)
        response = self._http.get(
            ACTIVITIES_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params,
        )
        if response.status_code == 401:  # stale token — refresh once, retry
            self.access_token = None
            self._ensure_token()
            response = self._http.get(
                ACTIVITIES_URL,
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
            )
        if response.status_code >= 400:
            raise StravaError(f"Strava activities failed (HTTP {response.status_code})")
        return response.json()


def map_activity(activity: dict) -> dict:
    """Strava activity → our log fields. Pace COMPUTED in code."""
    distance_km = float(activity["distance"]) / 1000.0
    moving_sec = float(activity["moving_time"])
    return {
        "date": (activity.get("start_date_local") or activity.get("start_date") or "")[:10],
        "session_type": "run",
        "distance_km": round(distance_km, 2),
        "moving_time_min": round(moving_sec / 60.0, 2),
        "avg_pace_sec_km": int(round(moving_sec * 1000.0 / float(activity["distance"])))
        if activity.get("distance") else None,
        "notes": (activity.get("name") or "")[:200],
    }


def last_sync_epoch(conn) -> int | None:
    row = conn.execute(
        "SELECT MAX(imported_at) AS last FROM strava_imports"
    ).fetchone()
    if not row["last"]:
        return None
    from datetime import datetime

    try:
        return int(datetime.strptime(row["last"], "%Y-%m-%d %H:%M:%S").timestamp())
    except ValueError:
        return None


def sync_activities(
    conn,
    client: StravaClient,
    *,
    user_id: int,
    since_epoch: int | None = None,
    limit: int = 100,
    now_epoch: int | None = None,
) -> dict:
    """Import new runs. Returns {"added": n, "skipped": n}."""
    now_epoch = int(now_epoch or time.time())
    # Dedup set from the imports table (full history).
    imported = {
        row["strava_id"]
        for row in conn.execute("SELECT strava_id FROM strava_imports")
    }
    activities = client.get_activities(after_epoch=since_epoch, per_page=limit)

    added = 0
    skipped = 0
    for activity in activities:
        if activity["id"] in imported or activity.get("type") != "Run":
            skipped += 1
            continue
        fields = map_activity(activity)
        log_id = save_log(
            conn,
            date=fields["date"] or "1970-01-01",
            user_id=user_id,
            user_input=f"strava sync: {fields['notes']}",
            ai_response="imported from Strava",
            session_type=fields["session_type"],
            distance_km=fields["distance_km"],
            moving_time_min=fields["moving_time_min"],
            completed=1,
            verified=1,
            prompt_version="strava-api-v1",
        )
        conn.execute(
            "INSERT INTO strava_imports (strava_id, log_id) VALUES (?, ?)",
            (activity["id"], log_id),
        )
        if fields["distance_km"] and fields["moving_time_min"]:
            conn.execute(
                "INSERT INTO performance_anchors (date, distance_km, time_sec, source, verified) "
                "VALUES (?, ?, ?, 'strava', 1)",
                (
                    fields["date"],
                    fields["distance_km"],
                    int(round(fields["moving_time_min"] * 60)),
                ),
            )
        added += 1
    conn.commit()
    return {"added": added, "skipped": skipped}
