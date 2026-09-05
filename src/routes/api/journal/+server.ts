import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getJournal, todayLocal, upsertJournal } from '$lib/server/plan_store';

export const GET: RequestHandler = async () => {
	const date = todayLocal();
	return json({ date, journal: await getJournal(date) });
};

export const PUT: RequestHandler = async ({ request }) => {
	try {
		const body = await request.json();
		const clamp = (n: unknown, lo: number, hi: number) => {
			if (n == null || n === '') return null;
			const v = Number(n);
			return Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : null;
		};
		await upsertJournal(todayLocal(), {
			energy: clamp(body?.energy, 1, 5),
			sleep_h: clamp(body?.sleep_h, 0, 16),
			soreness: ['none', 'mild', 'noticeable', 'sharp'].includes(body?.soreness) ? body.soreness : null,
			note: body?.note ? String(body.note).slice(0, 500) : null
		});
		return json({ ok: true, date: todayLocal(), journal: await getJournal(todayLocal()) });
	} catch (err) {
		throw error(400, err instanceof Error ? err.message : 'invalid journal entry');
	}
};
