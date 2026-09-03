import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { planView } from '$lib/server/plan_store';

export const POST: RequestHandler = async ({ request }) => {
	let horizonDays = 14;
	try {
		const body = await request.json();
		if (typeof body?.horizonDays === 'number') horizonDays = body.horizonDays;
	} catch {
		// no body -> defaults
	}
	horizonDays = Math.min(Math.max(horizonDays, 7), 42);
	try {
		return json(planView(horizonDays, true));
	} catch (err) {
		throw error(500, err instanceof Error ? err.message : 'plan generation failed');
	}
};
