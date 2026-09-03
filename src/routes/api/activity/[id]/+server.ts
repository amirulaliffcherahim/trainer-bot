import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { feedbackFor } from '$lib/server/plan_store';
import { reviewActivity } from '$lib/server/review';
import { latestSnapshot } from '$lib/server/fitness';
import { getDb } from '$lib/server/db';
import { apiGet } from '$lib/server/strava';
import type { ActivityRow } from '$lib/server/plan_store';

const STREAM_KEYS = ['time', 'distance', 'latlng', 'altitude', 'velocity_smooth'];

export const GET: RequestHandler = async ({ params }) => {
	const id = Number(params.id);
	if (!Number.isInteger(id) || id <= 0) throw error(400, 'activity id required');
	const row = getDb()
		.prepare(
			`SELECT strava_id, name, type, sport_type, start_date_local, distance, moving_time,
			        average_speed, average_heartrate, max_heartrate, has_heartrate, trainer, commute, manual
			 FROM activities WHERE strava_id = ?`
		)
		.get(id) as ActivityRow | undefined;
	if (!row) throw error(404, 'activity not found');

	const vdotVal = latestSnapshot()?.vdot ?? null;
	const fb = feedbackFor([row.strava_id]).get(row.strava_id) ?? null;

	// GPS streams, fetched live from Strava (single user — rate limits fine).
	let streams: Record<string, unknown[]> | null = null;
	let streamError: string | null = null;
	try {
		const { data } = await apiGet<Record<string, unknown[]>>(
			`/activities/${id}/streams?keys=${STREAM_KEYS.join(',')}&key_by_type=true`
		);
		streams = data;
	} catch (err) {
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
