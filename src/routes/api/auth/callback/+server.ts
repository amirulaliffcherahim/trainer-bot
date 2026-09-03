import { error, redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exchangeCode } from '$lib/server/strava';

export const GET: RequestHandler = async ({ url }) => {
	const code = url.searchParams.get('code');
	const denied = url.searchParams.get('error');
	if (denied) {
		throw redirect(303, `/?notice=${encodeURIComponent(`Strava auth ${denied}`)}`);
	}
	if (!code) {
		throw error(400, 'Missing authorization code');
	}
	try {
		await exchangeCode(code);
	} catch (err) {
		const msg = err instanceof Error ? err.message : 'exchange failed';
		throw redirect(303, `/?notice=${encodeURIComponent('Strava connect failed: ' + msg)}`);
	}
	throw redirect(303, '/?notice=connected');
};
