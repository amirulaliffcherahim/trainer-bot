import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const res = await fetch('/api/fitness');
	return (await res.json()) as {
		snapshot: {
			vdot: number;
			source_name?: string;
			source_distance: number;
			source_time_min: number;
			source_date: string | null;
		} | null;
		derived: {
			vdot: number;
			paces: {
				easy: { slow: number; fast: number };
				marathon: number;
				threshold: number;
				interval: number;
				repetition: number;
				fast_reps: number;
			};
			equivalents: Record<string, number>;
		} | null;
	};
};
