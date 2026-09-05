import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

/**
 * Storage facade regression — runs against the node:sqlite backend (no
 * DATABASE_URL → sqlite). Exercises named + positional params, transactions,
 * identity lastInsertRowid, ON CONFLICT, and the v6 JSON tables.
 */

let dir: string;
let db: typeof import('./db');
let dbPath: string;

beforeAll(async () => {
	dir = mkdtempSync(path.join(os.tmpdir(), 'tbdb-'));
	dbPath = path.join(dir, 't.db');
	process.env.DB_PATH = dbPath;
	delete process.env.DATABASE_URL;
	db = await import('./db');
});

afterAll(async () => {
	await db.closeDb();
	rmSync(dir, { recursive: true, force: true });
	delete process.env.DB_PATH;
});

describe('storage facade (sqlite)', () => {
	it('positional params + identity insert + lastInsertRowid', async () => {
		const r = await db.dbRun('INSERT INTO events (name, distance_m, event_date, created_at) VALUES (?, ?, ?, ?)', ['t', 5000, '2026-09-01', 1]);
		expect(r.lastInsertRowid).not.toBeNull();
		const row = await db.dbGet<{ name: string }>('SELECT name FROM events WHERE id = ?', [Number(r.lastInsertRowid)]);
		expect(row?.name).toBe('t');
	});

	it('named params (@name, keys without prefix)', async () => {
		await db.dbRun(
			`INSERT INTO feedback (strava_id, rpe, felt, note, created_at)
			 VALUES (@sid, @rpe, @felt, @note, @created)
			 ON CONFLICT(strava_id) DO UPDATE SET rpe=@rpe`,
			{ sid: 9001, rpe: 7, felt: 'hard', note: null, created: 1 }
		);
		const rows = await db.dbAll<{ strava_id: number; rpe: number }>('SELECT strava_id, rpe FROM feedback WHERE strava_id = ?', [9001]);
		expect(rows).toHaveLength(1);
		expect(rows[0].rpe).toBe(7);
	});

	it('multi-statement exec + transaction rollback', async () => {
		await db.dbExec('BEGIN');
		await db.dbRun('INSERT INTO events (name, distance_m, event_date, created_at) VALUES (?, ?, ?, ?)', ['tx', 5000, '2026-09-02', 1]);
		await db.dbExec('ROLLBACK');
		const n = await db.dbGet<{ n: number }>("SELECT COUNT(*) AS n FROM events WHERE name = 'tx'");
		expect(n?.n).toBe(0);
	});

	it('v6 JSON capture tables accept payloads', async () => {
		await db.dbRun(
			`INSERT INTO activity_detail (strava_id, payload, fetched_at) VALUES (?, ?, ?)
			 ON CONFLICT(strava_id) DO UPDATE SET payload=excluded.payload`,
			[9002, JSON.stringify({ splits_metric: [1, 2] }), 1]
		);
		const row = await db.dbGet<{ payload: string }>('SELECT payload FROM activity_detail WHERE strava_id = ?', [9002]);
		expect(JSON.parse(row!.payload).splits_metric).toEqual([1, 2]);
	});
});
