import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { feedbackFor } from '$lib/server/plan_store';
import { reviewActivity } from '$lib/server/review';
import { latestSnapshot } from '$lib/server/fitness';
import { dbGet, dbRun } from '$lib/server/db';
import { apiGet } from '$lib/server/strava';
import type { ActivityRow } from '$lib/server/plan_store';

const STREAM_KEYS = [
	'time', 'distance', 'latlng', 'altitude', 'velocity_smooth',
	'heartrate', 'cadence', 'temp', 'watts', 'moving', 'grade_smooth'
];

type Stored = { streams: string | null };

function unwrap(raw: Record<string, unknown> | null): Record<string, unknown> | null {
	if (!raw) return null;
	const out: Record<string, unknown> = {};
	for (const k of STREAM_KEYS) {
		const v = raw[k];
		out[k] = Array.isArray(v)
			? (v as unknown[])
			: Array.isArray((v as { data?: unknown[] })?.data)
				? ((v as { data: unknown[] }).data as unknown[])
				: null;
	}
	return out;
}

export const GET: RequestHandler = async ({ params }) => {
	const id = Number(params.id);
	if (!Number.isInteger(id) || id <= 0) throw error(400, 'activity id required');
	const row = await dbGet<ActivityRow>(
		`SELECT strava_id, name, type, sport_type, start_date_local, distance, moving_time,
		        average_speed, average_heartrate, max_heartrate, has_heartrate, trainer, commute, manual
		 FROM activities WHERE strava_id = ?`,
		[id]
	);
	if (!row) throw error(404, 'activity not found');

	const vdotVal = (await latestSnapshot())?.vdot ?? null;
	const fb = (await feedbackFor([row.strava_id])).get(row.strava_id) ?? null;

	// GPS streams: prefer the locally stored own-data copy (offline, no API
	// hit); fall back to a live Strava fetch and cache it for next time.
	let streams: Record<string, unknown[] | null> | null = null;
	let streamError: string | null = null;
	try {
		const stored = await dbGet<Stored>('SELECT streams FROM activity_streams WHERE strava_id = ?', [id]);
		if (stored?.streams) {
			const parsed = unwrap(JSON.parse(stored.streams) as Record<string, unknown>);
			if (parsed && Object.values(parsed).some((v) => Array.isArray(v) && (v as unknown[]).length > 0)) {
				streams = parsed as Record<string, unknown[] | null>;
			}
		}
		if (!streams) {
			const { data } = await apiGet<Record<string, { data?: unknown[] } | unknown[] | null>>(
				`/activities/${id}/streams?keys=${STREAM_KEYS.join(',')}&key_by_type=true`
			);
			streams = unwrap(data as Record<string, unknown>) as Record<string, unknown[] | null>;
			try {
				await dbRun(
					`INSERT INTO activity_streams (strava_id, streams, fetched_at) VALUES (?, ?, ?)
					 ON CONFLICT(strava_id) DO UPDATE SET streams=excluded.streams, fetched_at=excluded.fetched_at`,
					[id, JSON.stringify(data ?? null), Math.floor(Date.now() / 1000)]
				);
			} catch {
				// cache write is best-effort
			}
		}
	} catch (err) {
		streams = null;
		streamError = err instanceof Error ? err.message : 'streams unavailable';
	}

	return json({
		activity: {
			...row,
			pace_sec_km: row.moving_time > 0 && row.distance > 0 ? Math.round(row.moving_time / (row.distance / 1000)) : null,
			review: reviewActivity(row, vdotVal),
			feedback: fb,
			needs_feedback: !fb
		},
		streams,
		streamError
	});
};
