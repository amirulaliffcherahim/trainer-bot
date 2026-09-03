import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { listEvents, todayLocal } from '$lib/server/plan_store';
import { latestSnapshot } from '$lib/server/fitness';
import { raceBriefing } from '$lib/server/race';

export const GET: RequestHandler = () => {
	const event = listEvents()
		.filter((e) => e.event_date >= todayLocal())
		.sort((a, b) => a.event_date.localeCompare(b.event_date))[0] ?? null;
	if (!event) return json({ race: null });
	return json({ race: raceBriefing(event, latestSnapshot()?.vdot ?? null) });
};
