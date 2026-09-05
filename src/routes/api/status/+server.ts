import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getToken, tokenUsable } from '$lib/server/token_store';
import { activityCount } from '$lib/server/fitness';
import { stravaConfig } from '$lib/server/strava';

export const GET: RequestHandler = async () => {
	const token = await getToken();
	const configured = stravaConfig() !== null;
	const connected = token !== null;
	const scope = token?.scope ?? null;
	const canReadActivities = connected && !!scope && /activity:read(_all)?/.test(scope);
	return json({
		configured,
		connected,
		connected_athlete: token?.athlete_name ?? null,
		scopes: scope,
		can_read_activities: canReadActivities,
		token_usable: await tokenUsable(),
		token_expires_at: token?.expires_at ?? null,
		activity_count: await activityCount()
	});
};
