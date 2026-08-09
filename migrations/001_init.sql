-- 001: initial schema v2 (trainer bot)
-- Forward-only. Never edit an applied migration; add 002_*.sql instead.

CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_input TEXT,
    has_image INTEGER DEFAULT 0,
    image_path TEXT,
    ai_response TEXT NOT NULL,
    rpe INTEGER CHECK (rpe BETWEEN 1 AND 10),
    fatigue_level INTEGER CHECK (fatigue_level BETWEEN 1 AND 10),
    weight_kg REAL CHECK (weight_kg BETWEEN 30 AND 200),
    sleep_hours REAL,
    session_type TEXT,
    completed INTEGER DEFAULT 0,
    verified INTEGER DEFAULT 0,
    persona_drafts TEXT,
    model_used TEXT,
    prompt_version TEXT,
    raw_payload TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_daily_logs_date_user ON daily_logs (date, user_id);

CREATE TABLE IF NOT EXISTS athlete_profile (
    user_id INTEGER PRIMARY KEY,
    height_cm REAL,
    weight_kg REAL,
    target_race TEXT,
    target_pace TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS training_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    focus TEXT,
    volume_range TEXT,
    pace_target TEXT,
    rules_json TEXT
);

CREATE TABLE IF NOT EXISTS workout_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    day_type TEXT,
    session_type TEXT,
    description TEXT,
    prescribed_km REAL,
    target_pace TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weekly_rollups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL UNIQUE,
    volume_km REAL,
    avg_rpe REAL,
    avg_fatigue REAL,
    weight_trend REAL,
    completed_sessions INTEGER,
    long_run_km REAL
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona TEXT NOT NULL,
    title TEXT,
    source TEXT,
    content TEXT NOT NULL,
    embedding BLOB,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_persona ON kb_chunks (persona);

CREATE TABLE IF NOT EXISTS eval_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona TEXT,
    prompt TEXT NOT NULL,
    expected_facts TEXT,
    expected_advice TEXT,
    last_result TEXT
);

CREATE TABLE IF NOT EXISTS suggestions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    type TEXT NOT NULL,
    trigger TEXT,
    message TEXT,
    buttons TEXT,
    accepted INTEGER DEFAULT 0,
    dismissed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    persona TEXT,
    accepted INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS target_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    target_pace TEXT,
    predicted_pace TEXT,
    source TEXT,
    confirmed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS performance_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    distance_km REAL NOT NULL,
    time_sec INTEGER NOT NULL,
    source TEXT,
    verified INTEGER DEFAULT 0
);
