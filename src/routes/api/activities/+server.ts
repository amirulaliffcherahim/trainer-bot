import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { feedbackFor, recentActivities, saveFeedback } from '$lib/server/plan_store';
import { reviewActivity } from '$lib/server/review';
import { latestSnapshot } from '$lib/server/fitness';

export const GET: RequestHandler = () => {
	const acts = recentActivities(60);
	const vdotVal = latestSnapshot()?.vdot ?? null;
	const fb = feedbackFor(acts.map((a) => a.strava_id));
	return json({
		has_vdot: vdotVal !== null,
		activities: acts.map((a) => ({
			...a,
			pace_sec_km: a.moving_time > 0 && a.distance > 0 ? Math.round(a.moving_time / (a.distance / 1000)) : null,
			review: reviewActivity(a, vdotVal),
			feedback: fb.get(a.strava_id) ?? null,
			needs_feedback: !fb.has(a.strava_id)
		}))
	});
};

export const POST: RequestHandler = async ({ request }) => {
	try {
		const body = await request.json();
		const strava_id = Number(body?.strava_id);
		if (!Number.isInteger(strava_id) || strava_id <= 0) throw new Error('activity id required');
		saveFeedback({
			strava_id,
			rpe: body?.rpe != null && body.rpe !== '' ? Math.min(10, Math.max(1, Number(body.rpe))) : null,
			felt: body?.felt ? String(body.felt) : null,
			soreness: body?.soreness ? String(body.soreness) : null,
			note: body?.note ? String(body.note).slice(0, 500) : null
		});
		return json({ ok: true });
	} catch (err) {
		return json({ ok: false, message: err instanceof Error ? err.message : 'invalid feedback' }, { status: 400 });
	}
};
