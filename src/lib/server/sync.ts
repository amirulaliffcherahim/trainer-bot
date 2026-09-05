import { dbAll, dbGet, dbRun, dbExec } from './db';
import { apiGet } from './strava';

/**
 * Backfill + incremental import of activities.
 * See knowledge/strava_api/strava_api_research.md — paging by `before`
 * (epoch of the oldest row fetched so far), grouped by start_date_local.
 *
 * After the summary import, full-payload capture fills the own-data tables
 * (v6): per-activity DetailedActivity JSON + GPS streams, plus the athlete
 * profile + stats — capped per run to respect Strava's non-upload budget.
 */

const PER_PAGE = 100;
const MAX_PAGES = 60;
const STREAM_KEYS = [
	'time', 'distance', 'latlng', 'altitude', 'velocity_smooth',
	'heartrate', 'cadence', 'temp', 'watts', 'moving', 'grade_smooth'
];
/** max activities enriched per sync run (detail + streams = 2 calls each) */
const ENRICH_MAX = 40;

interface SummaryActivity {
	id: number;
	name?: string;
	type?: string;
	sport_type?: string;
	start_date?: string;
	start_date_local?: string;
	timezone?: string;
	distance?: number;
	moving_time?: number;
	elapsed_time?: number;
	total_elevation_gain?: number;
	average_speed?: number;
	max_speed?: number;
	average_heartrate?: number;
	max_heartrate?: number;
	has_heartrate?: boolean;
	calories?: number;
	trainer?: boolean;
	commute?: boolean;
	manual?: boolean;
	workout_type?: number;
	pr_count?: number;
}

async function upsert(a: SummaryActivity, nowSec: number): Promise<void> {
	await dbRun(
		`INSERT INTO activities (
			strava_id, name, type, sport_type, start_date, start_date_local,
			timezone, distance, moving_time, elapsed_time, total_elevation_gain,
			average_speed, max_speed, has_heartrate, average_heartrate,
			max_heartrate, calories, trainer, commute, manual, workout_type,
			pr_count, synced_at
		) VALUES (
			@strava_id, @name, @type, @sport_type, @start_date, @start_date_local,
			@timezone, @distance, @moving_time, @elapsed_time, @total_elevation_gain,
			@average_speed, @max_speed, @has_heartrate, @average_heartrate,
			@max_heartrate, @calories, @trainer, @commute, @manual, @workout_type,
			@pr_count, @synced_at
		)
		ON CONFLICT(strava_id) DO UPDATE SET
			name=@name, type=@type, sport_type=@sport_type,
			start_date=@start_date, start_date_local=@start_date_local,
			timezone=@timezone, distance=@distance, moving_time=@moving_time,
			elapsed_time=@elapsed_time, total_elevation_gain=@total_elevation_gain,
			average_speed=@average_speed, max_speed=@max_speed,
			has_heartrate=@has_heartrate, average_heartrate=@average_heartrate,
			max_heartrate=@max_heartrate, calories=@calories, trainer=@trainer,
			commute=@commute, manual=@manual, workout_type=@workout_type,
			pr_count=@pr_count, synced_at=@synced_at`,
		{
			strava_id: a.id,
			name: a.name ?? '',
			type: a.type ?? null,
			sport_type: a.sport_type ?? null,
			start_date: a.start_date ?? null,
			start_date_local: a.start_date_local ?? null,
			timezone: a.timezone ?? null,
			distance: a.distance ?? 0,
			moving_time: a.moving_time ?? 0,
			elapsed_time: a.elapsed_time ?? 0,
			total_elevation_gain: a.total_elevation_gain ?? 0,
			average_speed: a.average_speed ?? 0,
			max_speed: a.max_speed ?? 0,
			has_heartrate: a.has_heartrate ? 1 : 0,
			average_heartrate: a.average_heartrate ?? null,
			max_heartrate: a.max_heartrate ?? null,
			calories: a.calories ?? null,
			trainer: a.trainer ? 1 : 0,
			commute: a.commute ? 1 : 0,
			manual: a.manual ? 1 : 0,
			workout_type: a.workout_type ?? null,
			pr_count: a.pr_count ?? 0,
			synced_at: nowSec
		}
	);
}

export interface SyncResult {
	imported: number;
	pages: number;
	oldestDate: string | null;
	rateUsage: string | null;
	enriched: number;
}

/** Epoch seconds for the start of the current year (server-local time). */
export function yearStartEpochSec(now = new Date()): number {
	return new Date(now.getFullYear(), 0, 1).getTime() / 1000;
}

/* -------- full-payload capture (v6 tables) -------- */

function jsonCol(payload: unknown): string {
	return JSON.stringify(payload ?? null);
}

/** Which activities still need their detail + streams captured? */
async function pendingEnrich(nowSec: number, limit: number): Promise<number[]> {
	const rows = await dbAll<{ strava_id: number; synced_at: number }>(
		`SELECT a.strava_id, a.synced_at
		 FROM activities a
		 LEFT JOIN activity_detail d ON d.strava_id = a.strava_id
		 LEFT JOIN activity_streams s ON s.strava_id = a.strava_id
		 WHERE d.strava_id IS NULL OR d.fetched_at < a.synced_at
		    OR s.strava_id IS NULL OR s.fetched_at < a.synced_at
		 ORDER BY a.start_date_local DESC
		 LIMIT ?`,
		[limit]
	);
	return rows.map((r) => r.strava_id);
}

async function captureDetail(id: number, nowSec: number): Promise<void> {
	const { data } = await apiGet<Record<string, unknown>>(`/activities/${id}`);
	await dbRun(
		`INSERT INTO activity_detail (strava_id, payload, fetched_at) VALUES (?, ?, ?)
		 ON CONFLICT(strava_id) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at`,
		[id, jsonCol(data), nowSec]
	);
}

async function captureStreams(id: number, nowSec: number): Promise<void> {
	const { data } = await apiGet<Record<string, unknown>>(
		`/activities/${id}/streams?keys=${STREAM_KEYS.join(',')}&key_by_type=true`
	);
	await dbRun(
		`INSERT INTO activity_streams (strava_id, streams, fetched_at) VALUES (?, ?, ?)
		 ON CONFLICT(strava_id) DO UPDATE SET streams=excluded.streams, fetched_at=excluded.fetched_at`,
		[id, jsonCol(data), nowSec]
	);
	// mirror into the hypertable (activity_samples) for time-series queries
	const act = await dbGet<{ start_date: string | null }>('SELECT start_date FROM activities WHERE strava_id = ?', [id]);
	if (act?.start_date) await captureSamples(id, act.start_date, data).catch(() => undefined);
}

/** Unpack a key_by_type streams payload into hypertable sample rows and
 *  insert them (aligned by index on the `time` stream). Best-effort. */
async function captureSamples(id: number, startDateIso: string, raw: Record<string, unknown>): Promise<void> {
	const payload = raw as unknown as Record<string, { data?: unknown[] }>;
	const time = payload.time?.data;
	if (!Array.isArray(time) || time.length === 0) return;
	const n = time.length;
	const get = (k: string) => {
		const a = payload[k]?.data;
		return Array.isArray(a) && a.length === n ? (a as unknown[]) : null;
	};
	const dist = get('distance') as number[] | null;
	const alt = get('altitude') as number[] | null;
	const vel = get('velocity_smooth') as number[] | null;
	const hr = get('heartrate') as number[] | null;
	const cad = get('cadence') as number[] | null;
	const temp = get('temp') as number[] | null;
	const watts = get('watts') as number[] | null;
	const moving = get('moving') as boolean[] | null;
	const grade = get('grade_smooth') as number[] | null;
	const ll = get('latlng') as [number, number][] | null;
	const start = new Date(startDateIso);
	if (Number.isNaN(start.getTime())) return;
	const rows: unknown[] = [];
	const mk = (i: number) => {
		const p = ll?.[i];
		return [
			id,
			new Date(start.getTime() + (time[i] as number) * 1000),
			time[i],
			dist?.[i] ?? null,
			Array.isArray(p) ? p[0] : null,
			Array.isArray(p) ? p[1] : null,
			alt?.[i] ?? null,
			vel?.[i] ?? null,
			hr?.[i] != null ? Math.round(hr[i]) : null,
			cad?.[i] != null ? Math.round(cad[i]) : null,
			temp?.[i] != null ? Math.round(temp[i]) : null,
			watts?.[i] ?? null,
			moving?.[i] ?? null,
			grade?.[i] ?? null
		];
	};
	for (let i = 0; i < n; i++) rows.push(mk(i));
	const BATCH = 800;
	for (let i = 0; i < rows.length; i += BATCH) {
		const chunk = rows.slice(i, i + BATCH);
		const placeholders = chunk
			.map((_, r) => `(${chunk[0].map((_, c) => `$${r * chunk[0].length + c + 1}`).join(',')})`)
			.join(',');
		await dbRun(
			`INSERT INTO activity_samples (activity_id, ts, t_sec, dist_m, lat, lng, alt_m, vel_m_s, hr, cad, temp_c, watts, moving, grade)
			 VALUES ${placeholders} ON CONFLICT DO NOTHING`,
			chunk.flat()
		);
	}
}

async function captureAthlete(nowSec: number): Promise<void> {
	try {
		const { data: profile } = await apiGet<Record<string, unknown>>('/athlete');
		const athleteId = typeof profile?.id === 'number' ? profile.id : null;
		let stats: Record<string, unknown> | null = null;
		if (athleteId !== null) {
			try {
				const r = await apiGet<Record<string, unknown>>(`/athletes/${athleteId}/stats`);
				stats = r.data ?? null;
			} catch {
				stats = null;
			}
		}
		await dbRun(
			`INSERT INTO athlete_snapshot (id, payload, fetched_at) VALUES (1, ?, ?)
			 ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at`,
			[jsonCol({ profile, stats }), nowSec]
		);
	} catch {
		// profile fetch can fail (scope) — never fail the whole sync on it
	}
}

export async function syncActivities(cutoffEpochSec?: number): Promise<SyncResult> {
	const nowSec = Math.floor(Date.now() / 1000);
	// Default window: everything since Jan 1 of this year (user directive),
	// not just the trailing 180 days.
	const cutoff = cutoffEpochSec ?? yearStartEpochSec();
	let imported = 0;
	let pages = 0;
	let oldestDate: string | null = null;
	let usage: string | null = null;

	let before = nowSec; // Strava `before` is exclusive
	for (;;) {
		if (pages >= MAX_PAGES) break;
		const { data, rateUsage } = await apiGet<SummaryActivity[]>(
			`/athlete/activities?per_page=${PER_PAGE}&before=${before}`
		);
		usage = rateUsage.limit15;
		pages += 1;
		if (data.length === 0) break;

		const beforeCount = ((await dbGet<{ n: number }>('SELECT COUNT(*) AS n FROM activities'))?.n ?? 0) as number;
		await dbExec('BEGIN');
		try {
			for (const a of data) await upsert(a, nowSec);
			await dbExec('COMMIT');
		} catch (err) {
			await dbExec('ROLLBACK');
			throw err;
		}
		const afterCount = ((await dbGet<{ n: number }>('SELECT COUNT(*) AS n FROM activities'))?.n ?? 0) as number;
		imported += Math.max(0, afterCount - beforeCount);

		// oldest activity of this page (grouping by start_date_local)
		let oldest = data[data.length - 1];
		for (const a of data) {
			if ((a.start_date_local ?? '') < (oldest.start_date_local ?? '')) oldest = a;
		}
		oldestDate = oldest.start_date_local ?? null;
		const t = new Date(oldest.start_date ?? oldest.start_date_local ?? Date.now()).getTime();
		before = t / 1000;

		if (before <= cutoff) break; // reached the window we care about
		await new Promise((r) => setTimeout(r, 400)); // polite pacing
	}

	// ---- full-payload capture (incremental) ----
	let enriched = 0;
	const toEnrich = await pendingEnrich(nowSec, ENRICH_MAX);
	await captureAthlete(nowSec).catch(() => undefined);
	for (const id of toEnrich) {
		try {
			await captureDetail(id, nowSec);
			await new Promise((r) => setTimeout(r, 300));
			await captureStreams(id, nowSec);
			await new Promise((r) => setTimeout(r, 300));
			enriched += 1;
		} catch {
			// individual capture failures are non-fatal; retried next sync
		}
	}

	return { imported, pages, oldestDate, rateUsage: usage, enriched };
}
