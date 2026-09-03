import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fitnessView } from '$lib/server/fitness';

export const GET: RequestHandler = () => {
	return json(fitnessView());
};
