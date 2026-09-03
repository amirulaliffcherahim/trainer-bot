import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { LEGACY_PREFS, type PlanPrefs } from '$lib/server/plan';
import { loadPrefs, savePrefs } from '$lib/server/plan_store';

export const GET: RequestHandler = () => {
	return json(loadPrefs() ?? LEGACY_PREFS);
};

export const PUT: RequestHandler = async ({ request }) => {
	try {
		const body = (await request.json()) as Partial<PlanPrefs>;
		if (!Array.isArray(body?.runDays) || !Array.isArray(body?.hardDays)) throw new Error('runDays and hardDays arrays required');
		const prefs: PlanPrefs = {
			runDays: body.runDays.map(Number),
			hardDays: body.hardDays.map(Number),
			...(body.kinds && Object.keys(body.kinds).length > 0 ? { kinds: body.kinds as PlanPrefs['kinds'] } : {})
		};
		savePrefs(prefs);
		return json(loadPrefs());
	} catch (err) {
		throw error(400, err instanceof Error ? err.message : 'invalid prefs');
	}
};
