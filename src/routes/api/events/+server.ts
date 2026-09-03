import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { addEvent, deleteEvent, listEvents } from '$lib/server/plan_store';

export const GET: RequestHandler = () => json(listEvents());

export const POST: RequestHandler = async ({ request }) => {
		try {
			const body = await request.json();
			const ev = addEvent({
				name: String(body?.name ?? '').trim(),
				distance_m: Number(body?.distance_m),
				event_date: String(body?.event_date ?? ''),
				target_time_min: body?.target_time_min != null && body.target_time_min !== '' ? Number(body.target_time_min) : null,
				category: body?.category ? String(body.category) : null
			});
			return json(ev, { status: 201 });
		} catch (err) {
			throw error(400, err instanceof Error ? err.message : 'invalid event');
		}
	};

export const DELETE: RequestHandler = async ({ url }) => {
	const id = Number(url.searchParams.get('id'));
	if (!Number.isInteger(id) || id <= 0) throw error(400, 'event id required');
	if (!deleteEvent(id)) throw error(404, 'event not found');
	return json({ ok: true });
};
