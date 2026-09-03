import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { planView } from '$lib/server/plan_store';

export const GET: RequestHandler = async ({ url }) => {
	const days = Math.min(Math.max(parseInt(url.searchParams.get('days') ?? '14', 10) || 14, 7), 42);
	return json(planView(days, false));
};
