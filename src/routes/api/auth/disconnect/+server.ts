import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { disconnect } from '$lib/server/strava';

export const POST: RequestHandler = async () => {
	await disconnect();
	return json({ ok: true });
};
