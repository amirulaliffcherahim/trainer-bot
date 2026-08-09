-- 004: notifications (scheduler) — dedup log + per-type preferences.

CREATE TABLE IF NOT EXISTS sent_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    date TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE (type, user_id, date)
);

CREATE TABLE IF NOT EXISTS notification_prefs (
    user_id INTEGER PRIMARY KEY,
    run_reminders INTEGER DEFAULT 1,
    recap INTEGER DEFAULT 1,
    suggestions INTEGER DEFAULT 1
);
