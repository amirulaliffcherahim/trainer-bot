-- 006: direct Strava sync — import dedup + tiny key-value store
-- (kv_store persists the ROTATED Strava refresh token).

CREATE TABLE IF NOT EXISTS strava_imports (
    strava_id INTEGER PRIMARY KEY,
    log_id INTEGER,
    imported_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kv_store (
    key TEXT PRIMARY KEY,
    value TEXT
);
