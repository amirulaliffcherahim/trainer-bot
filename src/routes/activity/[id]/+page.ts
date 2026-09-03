import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const res = await fetch(`/api/activity/${params.id}`);
	if (!res.ok) {
		return { missing: true };
	}
	return await res.json();
};
