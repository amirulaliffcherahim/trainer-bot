import { json, redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { authorizeUrl, stravaConfig } from '$lib/server/strava';

export const GET: RequestHandler = () => {
	if (!stravaConfig()) {
		return json({ error: 'Strava not configured. Register your app at strava.com/settings/api and set STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET.' }, { status: 503 });
	}
	throw redirect(302, authorizeUrl());
};
