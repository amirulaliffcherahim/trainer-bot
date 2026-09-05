import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getToken } from '$lib/server/token_store';
import { syncActivities } from '$lib/server/sync';
import { recomputeFitness, latestSnapshot } from '$lib/server/fitness';
import { StravaError } from '$lib/server/strava';

export const POST: RequestHandler = async () => {
	if (!(await getToken())) {
		throw error(401, 'Not connected to Strava');
	}
	try {
		const result = await syncActivities();
		const snapshot = (await recomputeFitness(Math.floor(Date.now() / 1000))) ?? (await latestSnapshot());
		return json({
			synced: result,
			snapshot,
			summary:
				snapshot === null
					? 'Synced, but no PB-able effort found in recent activities yet.'
					: `Fitness anchor (est. VO₂ max): ${snapshot.vdot.toFixed(1)}`
		});
	} catch (err) {
		if (err instanceof StravaError) {
			throw error(502, err.message);
		}
		throw error(500, err instanceof Error ? err.message : 'sync failed');
	}
};
