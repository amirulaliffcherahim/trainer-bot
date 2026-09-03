import { getDb } from './db';
import { build_result, vdot, type VdotResult } from '../vdot';

/** PB scan → VO₂ anchor (est.).
 * Only your 5K PR feeds the anchor (user directive) — distance must sit in
 * the 5K bucket (±15%); flags manual/trainer/commute excluded; recency
 * window limits staleness.
 */

export const RECENCY_DAYS = 120;
export const BUCKETS_M = [5000];

interface ActivityRow {
	strava_id: number;
	name: string;
	distance: number;
	moving_time: number;
	start_date_local: string | null;
	average_heartrate: number | null;
}

export interface FitnessSnapshot {
	id: number;
	vdot: number;
	source_strava_id: number;
	source_distance: number;
	source_time_min: number;
	source_date: string | null;
	source_name?: string;
	created_at: number;
}

/** Pick the best-effort activity rows within the recency window. */
export function candidateEfforts(nowSec: number): ActivityRow[] {
	const cutoff = new Date((nowSec - RECENCY_DAYS * 86400) * 1000).toISOString();
	const rows = getDb()
		.prepare(
			`SELECT strava_id, name, distance, moving_time, start_date_local, average_heartrate
			 FROM activities
			 WHERE trainer = 0 AND commute = 0 AND manual = 0
			   AND moving_time > 0 AND moving_time <= 4 * 3600
			   AND distance >= 4000 AND distance <= 60000
			   AND COALESCE(start_date, '') >= ?
			 ORDER BY distance`
		)
		.all(cutoff) as unknown as ActivityRow[];
	const bestByBucket = new Map<number, ActivityRow>();
	for (const r of rows) {
		// nearest bucket within ±15%
		let nearest: number | null = null;
		let bestRatio = Infinity;
		for (const b of BUCKETS_M) {
			const ratio = Math.abs(r.distance - b) / b;
			if (ratio < bestRatio) {
				bestRatio = ratio;
				nearest = b;
			}
		}
		if (nearest === null || bestRatio > 0.15) continue;
		const cur = bestByBucket.get(nearest);
		if (!cur || vdot(r.distance, r.moving_time / 60) > vdot(cur.distance, cur.moving_time / 60)) {
			bestByBucket.set(nearest, r);
		}
	}
	return [...bestByBucket.values()];
}

/** Compute + persist a snapshot if the best VDOT improved (or is new). */
export function recomputeFitness(nowSec: number): FitnessSnapshot | null {
	const efforts = candidateEfforts(nowSec);
	if (efforts.length === 0) return null;
	let best: { row: ActivityRow; vdot: number } | null = null;
	for (const r of efforts) {
		const v = vdot(r.distance, r.moving_time / 60);
		if (!best || v > best.vdot) best = { row: r, vdot: v };
	}
	if (!best) return null;

	const db = getDb();
	const latest = latestSnapshot();
	const changed =
		!latest ||
		Math.abs(latest.vdot - best.vdot) > 0.05 ||
		latest.source_strava_id !== best.row.strava_id;

	if (changed) {
		const res = db
			.prepare(
				`INSERT INTO vdot_snapshots
				 (vdot, source_strava_id, source_distance, source_time_min, source_date, created_at)
				 VALUES (?, ?, ?, ?, ?, ?)`
			)
			.run(
				best.vdot,
				best.row.strava_id,
				best.row.distance,
				best.row.moving_time / 60,
				best.row.start_date_local?.slice(0, 10) ?? null,
				nowSec
			);
		return snapshotById(Number(res.lastInsertRowid));
	}
	return latest;
}

export function latestSnapshot(): FitnessSnapshot | null {
	return snapshotById(
		(
			getDb().prepare('SELECT MAX(id) AS id FROM vdot_snapshots').get() as { id: number | null }
		).id
	);
}

export function snapshotById(id: number | null): FitnessSnapshot | null {
	if (id === null) return null;
	const row = getDb()
		.prepare(
			`SELECT s.*, a.name AS source_name
			 FROM vdot_snapshots s LEFT JOIN activities a ON a.strava_id = s.source_strava_id
			 WHERE s.id = ?`
		)
		.get(id) as (FitnessSnapshot & { source_name: string | null }) | undefined;
	if (!row) return null;
	const { source_name, ...rest } = row;
	return { ...rest, source_name: source_name ?? undefined };
}

/** Snapshot + derived VDOT table for the Fitness view. */
export function fitnessView(): { snapshot: FitnessSnapshot | null; derived: VdotResult | null } {
	const s = latestSnapshot();
	return { snapshot: s, derived: s ? build_result(s.vdot) : null };
}

export function activityCount(): number {
	return (getDb().prepare('SELECT COUNT(*) AS n FROM activities').get() as { n: number }).n;
}
