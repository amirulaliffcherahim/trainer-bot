import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { swapSessionKind } from '$lib/server/plan_store';
import type { Session } from '$lib/server/plan';

const ALLOWED: Session['kind'][] = ['easy', 'quality', 'interval', 'long'];

export const PUT: RequestHandler = async ({ request }) => {
	try {
		const body = await request.json();
		const planDate = String(body?.plan_date ?? '');
		const kind = String(body?.kind ?? '') as Session['kind'];
		if (!/^\d{4}-\d{2}-\d{2}$/.test(planDate)) throw new Error('valid plan_date required');
		if (!ALLOWED.includes(kind)) throw new Error('kind must be easy, quality, interval or long');
		if (!swapSessionKind(planDate, kind)) throw new Error('no swappable session on that date (rest/race days are fixed)');
		return json({ ok: true });
	} catch (err) {
		throw error(400, err instanceof Error ? err.message : 'invalid swap');
	}
};
