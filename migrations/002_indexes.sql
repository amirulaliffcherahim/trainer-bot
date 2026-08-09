-- 002: additional indexes (Phase 1 review — query optimization for /today
-- and race prediction).

CREATE INDEX IF NOT EXISTS idx_workout_plan_date ON workout_plan (date);

CREATE INDEX IF NOT EXISTS idx_perf_anchors_verified_dist
    ON performance_anchors (verified, distance_km);
