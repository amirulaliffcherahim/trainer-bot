import { getToken } from './token_store';
import { syncActivities, yearStartEpochSec } from './sync';
import { recomputeFitness } from './fitness';
import { getDb } from './db';

/**
 * Hourly auto-sync (single-user). Started once at server boot from
 * hooks.server.ts init(). Guards: only when connected with activity scope,
 * never overlapping a previous run, no crash on Strava/network errors.
 */

export const HOURLY_MS = 60 * 60 * 1000;

let running = false;
let timer: ReturnType<typeof setInterval> | null = null;

async function tick(): Promise<void> {
	if (running) return;
	const t = getToken();
	if (!t || !/activity:read(_all)?/.test(t.scope ?? '')) return;
	running = true;
	try {
		const res = await syncActivities(yearStartEpochSec());
		const snap = recomputeFitness(Math.floor(Date.now() / 1000));
		const count = (getDb().prepare('SELECT COUNT(*) AS n FROM activities').get() as { n: number }).n;
		console.log(
			`[sync-hourly] pages=${res.pages} imported=${res.imported} total=${count} ` +
				`vdot=${snap ? snap.vdot.toFixed(1) : 'none'}`,
		);
	} catch (err) {
		console.error('[sync-hourly] failed:', err instanceof Error ? err.message : err);
	} finally {
		running = false;
	}
}

/** Start the hourly loop; safe to call more than once. */
export function startHourlySync(): void {
	if (timer) return;
	timer = setInterval(() => {
		void tick();
	}, HOURLY_MS);
	// keep the process alive-friendly & first tick shortly after boot
	timer.unref?.();
	setTimeout(() => void tick(), 30_000);
}
