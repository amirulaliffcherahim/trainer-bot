import { DatabaseSync } from 'node:sqlite';

/**
 * Single-user SQLite via node:sqlite (Node >= 22.5 built-in — no native
 * module build needed). Hand-written schema + forward-only migrations using
 * PRAGMA user_version (mirrors the old db.py pattern).
 */

export interface AppDb {
	conn: DatabaseSync;
	close: () => void;
}

let singleton: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
	if (singleton) return singleton;
	const path = process.env.DB_PATH || 'trainer.db';
	const conn = new DatabaseSync(path);
	conn.exec('PRAGMA journal_mode = WAL;');
	conn.exec('PRAGMA foreign_keys = ON;');
	migrate(conn);
	singleton = conn;
	return conn;
}

const MIGRATIONS: string[] = [
	// v1 — initial schema
	`
	CREATE TABLE strava_token (
		id INTEGER PRIMARY KEY CHECK (id = 1),
		access_token TEXT NOT NULL,
		refresh_token TEXT NOT NULL,
		expires_at INTEGER NOT NULL,        -- epoch seconds
		scope TEXT NOT NULL DEFAULT '',
		athlete_id INTEGER,
		athlete_name TEXT,
		updated_at INTEGER NOT NULL
	);

	CREATE TABLE activities (
		id INTEGER PRIMARY KEY,
		strava_id INTEGER NOT NULL UNIQUE,
		name TEXT NOT NULL DEFAULT '',
		type TEXT,
		sport_type TEXT,
		start_date TEXT,                    -- UTC ISO
		start_date_local TEXT,              -- athlete-local ISO (day grouping!)
		timezone TEXT,
		distance REAL NOT NULL DEFAULT 0,   -- meters
		moving_time INTEGER NOT NULL DEFAULT 0,  -- seconds
		elapsed_time INTEGER NOT NULL DEFAULT 0,
		total_elevation_gain REAL DEFAULT 0,
		average_speed REAL DEFAULT 0,       -- m/s
		max_speed REAL DEFAULT 0,
		has_heartrate INTEGER NOT NULL DEFAULT 0,
		average_heartrate REAL,
		max_heartrate REAL,
		calories REAL,
		trainer INTEGER NOT NULL DEFAULT 0,
		commute INTEGER NOT NULL DEFAULT 0,
		manual INTEGER NOT NULL DEFAULT 0,
		workout_type INTEGER,
		pr_count INTEGER DEFAULT 0,
		synced_at INTEGER NOT NULL
	);
	CREATE INDEX idx_activities_start_local ON activities(start_date_local);
	CREATE INDEX idx_activities_distance ON activities(distance);

	CREATE TABLE vdot_snapshots (
		id INTEGER PRIMARY KEY,
		vdot REAL NOT NULL,
		source_strava_id INTEGER NOT NULL,
		source_distance REAL NOT NULL,      -- meters
		source_time_min REAL NOT NULL,      -- moving time, minutes
		source_date TEXT,                   -- activity start_date_local date
		created_at INTEGER NOT NULL
	);
	`,
	// v2 — events + plan (S2)
	`
	CREATE TABLE events (
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		distance_m REAL NOT NULL,
		event_date TEXT NOT NULL,           -- 'YYYY-MM-DD' athlete-local
		target_time_min REAL,               -- optional; null -> predict from VDOT
		created_at INTEGER NOT NULL
	);

	CREATE TABLE planned_sessions (
		id INTEGER PRIMARY KEY,
		plan_date TEXT NOT NULL,            -- 'YYYY-MM-DD' athlete-local
		kind TEXT NOT NULL,                 -- easy|quality|interval|long|rest|race|recovery
		label TEXT NOT NULL DEFAULT '',
		distance_m REAL,                    -- meters (null when no VDOT anchor)
		duration_min REAL,
		pace_min_s_km REAL,                 -- faster bound, seconds/km
		pace_max_s_km REAL,                 -- slower bound, seconds/km
		plan_week TEXT NOT NULL DEFAULT '', -- e.g. 2026-W36 or phase label
		reason TEXT NOT NULL DEFAULT '',    -- KB citation
		created_at INTEGER NOT NULL
	);
	CREATE INDEX idx_planned_date ON planned_sessions(plan_date);
	`,
	// v3 — plan preferences, feedback, event category
	`
	ALTER TABLE events ADD COLUMN category TEXT;

	CREATE TABLE plan_prefs (
		id INTEGER PRIMARY KEY CHECK (id = 1),
		run_days TEXT NOT NULL,     -- JSON array of weekday ints (0=Sun..6=Sat)
		hard_days TEXT NOT NULL,    -- JSON array of weekday ints (subset of run_days)
		updated_at INTEGER NOT NULL
	);

	CREATE TABLE feedback (
		id INTEGER PRIMARY KEY,
		strava_id INTEGER NOT NULL UNIQUE,
		rpe INTEGER,                -- felt effort 1..10
		felt TEXT,                  -- easy|on|hard
		soreness TEXT,              -- none|mild|noticeable|sharp
		note TEXT,
		created_at INTEGER NOT NULL
	);
	`,
	// v4 — daily journal (S3)
	`
	CREATE TABLE journal (
		date TEXT PRIMARY KEY,      -- 'YYYY-MM-DD' athlete-local
		energy INTEGER,             -- 1..5
		sleep_h REAL,
		soreness TEXT,              -- none|mild|noticeable|sharp
		note TEXT,
		updated_at INTEGER NOT NULL
	);
	`,
	// v5 — per-day workout kinds (user picks speed/long/tempo/easy)
	`
	ALTER TABLE plan_prefs ADD COLUMN kinds TEXT;
	`
];

function migrate(conn: DatabaseSync): void {
	const row = conn.prepare('PRAGMA user_version').get() as { user_version: number };
	let version = row.user_version;
	while (version < MIGRATIONS.length) {
		conn.exec('BEGIN');
		try {
			conn.exec(MIGRATIONS[version]);
			version += 1;
			conn.exec(`PRAGMA user_version = ${version}`);
			conn.exec('COMMIT');
		} catch (err) {
			conn.exec('ROLLBACK');
			throw err;
		}
	}
}
