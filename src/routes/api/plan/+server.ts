import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { planView } from '$lib/server/plan_store';

export const GET: RequestHandler = async ({ url }) => {
	const raw = url.searchParams.get('days');
	// no days -> full horizon (current month, or race date when a race is set)
	const days = raw ? Math.max(parseInt(raw, 10) || 7, 1) : null;
	return json(planView(days, false));
};
