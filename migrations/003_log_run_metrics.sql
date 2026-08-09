-- 003: run metrics on daily_logs (Phase 2 — volume rollups and pace trends
-- need per-log distance/time; avg_pace_sec_km is computed by code on save,
-- never read from the LLM).

ALTER TABLE daily_logs ADD COLUMN distance_km REAL CHECK (distance_km > 0 AND distance_km <= 100);
ALTER TABLE daily_logs ADD COLUMN moving_time_min REAL CHECK (moving_time_min > 0 AND moving_time_min <= 600);
ALTER TABLE daily_logs ADD COLUMN avg_pace_sec_km INTEGER CHECK (avg_pace_sec_km > 0);

CREATE INDEX IF NOT EXISTS idx_daily_logs_user_date ON daily_logs (user_id, date);
