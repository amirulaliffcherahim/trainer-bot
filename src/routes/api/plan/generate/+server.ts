import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { planView } from '$lib/server/plan_store';

/** (Re)generate the full stored plan. The horizon is computed server-side —
 *  current month, or through the active race's date — never taken from the client. */
export const POST: RequestHandler = async () => {
	try {
		return json(planView(null, true));
	} catch (err) {
		throw error(500, err instanceof Error ? err.message : 'plan generation failed');
	}
};
