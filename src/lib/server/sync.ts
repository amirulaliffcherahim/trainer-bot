import { getDb } from './db';
import { apiGet } from './strava';

/**
 * Backfill + incremental import of activities.
 * See knowledge/strava_api/strava_api_research.md — paging by `before`
 * (epoch of the oldest row fetched so far), grouped by start_date_local.
 */

const PER_PAGE = 100;
const MAX_PAGES = 60;

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

function upsert(a: SummaryActivity, nowSec: number): void {
	getDb()
		.prepare(
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
				pr_count=@pr_count, synced_at=@synced_at`
		)
		.run({
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
		});
}

export interface SyncResult {
	imported: number;
	pages: number;
	oldestDate: string | null;
	rateUsage: string | null;
}

/** Pull activities back to `cutoffEpochSec` (default: 180 days). */
/** Epoch seconds for the start of the current year (server-local time). */
export function yearStartEpochSec(now = new Date()): number {
	return new Date(now.getFullYear(), 0, 1).getTime() / 1000;
}

export async function syncActivities(cutoffEpochSec?: number): Promise<SyncResult> {
	const nowSec = Math.floor(Date.now() / 1000);
	// Default window: everything since Jan 1 of this year (user directive),
	// not just the trailing 180 days.
	const cutoff = cutoffEpochSec ?? yearStartEpochSec();
	const db = getDb();
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

		const beforeCount = db.prepare('SELECT COUNT(*) AS n FROM activities').get() as { n: number };
		db.exec('BEGIN');
		try {
			for (const a of data) upsert(a, nowSec);
			db.exec('COMMIT');
		} catch (err) {
			db.exec('ROLLBACK');
			throw err;
		}
		const afterCount = db.prepare('SELECT COUNT(*) AS n FROM activities').get() as { n: number };
		imported += Math.max(0, afterCount.n - beforeCount.n);

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
	return { imported, pages, oldestDate, rateUsage: usage };
}
