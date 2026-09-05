import type { Session } from './plan';

/**
 * Matcher — plan vs reality, pure.
 * Day key = athlete-local date (start_date_local.slice(0,10)) — never UTC.
 * Run candidates exclude trainer/manual/commute activities.
 */

export interface ActBrief {
	strava_id: number;
	name: string;
	distance: number; // meters
	start_date_local: string | null; // ISO with tz; local date = slice(0,10)
	trainer: number;
	commute: number;
	manual: number;
}

export type MatchStatus = 'done' | 'partial' | 'missed' | 'extra' | 'planned';

export interface MatchedDay {
	date: string;
	planned: { session: Session; status: MatchStatus }[];
	extras: { strava_id: number; name: string; distance: number }[];
}

const isRunKind = (k: Session['kind']) => k !== 'rest';

/** Match planned sessions to activities, grouped by athlete-local date.
 *  Pass `today` (athlete-local 'YYYY-MM-DD') so days AFTER today stay
 *  unevaluated ('planned') instead of being flagged missed/done early. */
export function matchPlan(sessions: Session[], acts: ActBrief[], today?: string): MatchedDay[] {
	const byDate = new Map<string, ActBrief[]>();
	for (const a of acts) {
		const date = a.start_date_local?.slice(0, 10);
		if (!date) continue;
		const list = byDate.get(date) ?? [];
		list.push(a);
		byDate.set(date, list);
	}

	const dates = [...new Set(sessions.map((s) => s.plan_date))].sort();
	return dates.map((date) => {
		const dayActs = byDate.get(date) ?? [];
		const runs = dayActs
			.filter((a) => !a.trainer && !a.commute && !a.manual && a.distance > 0)
			.sort((a, b) => b.distance - a.distance);

		const planned = sessions
			.filter((s) => s.plan_date === date)
			.map((session): { session: Session; status: MatchStatus } => {
				if (today && date > today) return { session, status: 'planned' };
				if (session.kind === 'rest') {
					return { session, status: runs.length > 0 ? 'extra' : 'done' };
				}
				if (runs.length === 0) return { session, status: 'missed' };
				const best = runs[0].distance;
				if (session.distance_m === null || session.distance_m <= 0) {
					return { session, status: 'done' }; // no distance target — any run counts
				}
				const ratio = best / session.distance_m;
				return { session, status: ratio >= 0.9 ? 'done' : ratio >= 0.5 ? 'partial' : 'missed' };
			});

		// Extras = runs not consumed by a run-session match, or any run on a
		// day whose plan has no run session (rest-flag included on rest rows).
		const hasRunTarget = planned.some((p) => isRunKind(p.session.kind) && p.status !== 'missed');
		const consumed = hasRunTarget ? runs[0]?.strava_id : null;
		const extras = runs
			.filter((r) => r.strava_id !== consumed)
			.map((r) => ({ strava_id: r.strava_id, name: r.name, distance: r.distance }));

		return { date, planned, extras };
	});
}
