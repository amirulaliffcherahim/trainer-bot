import type { PageLoad } from './$types';

/** Full horizon — server computes it: current month, or through the race. */
export const load: PageLoad = async ({ fetch }) => {
	const res = await fetch('/api/plan');
	return await res.json();
};
