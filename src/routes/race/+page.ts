import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	return await (await fetch('/api/race')).json();
};
