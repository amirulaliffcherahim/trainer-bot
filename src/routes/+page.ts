import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [statusRes, fitnessRes, planRes, journalRes] = await Promise.all([
		fetch('/api/status'),
		fetch('/api/fitness'),
		fetch('/api/plan?days=7'),
		fetch('/api/journal')
	]);
	return {
		status: await statusRes.json(),
		fitness: await fitnessRes.json(),
		plan: await planRes.json(),
		journal: await journalRes.json()
	};
};
