import type { Session } from './plan';
import type { Feedback } from './plan_store';

/**
 * S3 — adjustment rules (feedback/journal -> plan). Pure & deterministic.
 *
 * Sources: daily journal (energy/soreness/sleep), feedback on the most recent
 * workout, and the matcher (missed yesterday). Adjustments apply only to
 * TODAY and TOMORROW — never re-roll the whole window — and the most severe
 * applicable rule wins. Rules are KB-grounded (physio triage, rest-day
 * rules, volume caps).
 */

export interface JournalState {
	energy: number | null; // 1..5
	sleep_h: number | null;
	soreness: 'none' | 'mild' | 'noticeable' | 'sharp' | null;
}

export interface AdjustCtx {
	journal: JournalState | null; // today's check-in
	last: (Feedback & { date: string; plannedKind: string | null }) | null; // most recent rated workout
	missedYesterday: boolean;
}

export interface AdjustOutcome {
	/** copies of the first two sessions (today, tomorrow), adjusted if needed */
	sessions: Session[];
	/** human notes explaining what the coach did / decided */
	notes: string[];
}

const HARD_KINDS: ReadonlySet<Session['kind']> = new Set(['quality', 'interval', 'long']);

/** Downgrade a run session to an easy run at `factor` of its distance. */
function downgrade(s: Session, factor: number, why: string): Session {
	if (s.kind === 'rest' || s.kind === 'race' || s.distance_m == null) return s;
	return {
		...s,
		kind: 'easy',
		label: 'Easy run (adjusted)',
		distance_m: Math.round((s.distance_m * factor) / 50) * 50,
		duration_min: null,
		pace_min_s_km: null,
		pace_max_s_km: null,
		reason: `${why} — ${Math.round(factor * 100)}% volume`
	};
}

export function adjust(today: Session[], ctx: AdjustCtx): AdjustOutcome {
	if (today.length === 0) return { sessions: [], notes: [] };
	const out: Session[] = today.slice(0, 2);
	const notes: string[] = [];
	const [todayS, tomorrowS] = [out[0], out[1]];
	const j = ctx.journal;

	/* Rule 0 — red flag (physio triage): sharp pain -> rest today, easy tomorrow. */
	if (j?.soreness === 'sharp') {
		if (todayS.kind !== 'rest') {
			out[0] = {
				...todayS,
				kind: 'rest',
				label: 'Rest — red flag',
				distance_m: null,
				duration_min: null,
				pace_min_s_km: null,
				pace_max_s_km: null,
				reason: 'physio/triage.md — sharp pain: stop. Sharp pain is not DOMS.'
			};
			notes.push('Sharp soreness flagged — training today is cancelled (physio triage).');
		}
		if (tomorrowS && HARD_KINDS.has(tomorrowS.kind)) {
			out[1] = downgrade(tomorrowS, 0.6, 'protecting the day after a red flag');
			notes.push('Tomorrow’s hard session downgraded to an easy run.');
		}
		return { sessions: out, notes };
	}

	/* Rule 1 — noticeable soreness: today's hard session becomes easy at 60%. */
	if (j?.soreness === 'noticeable' && HARD_KINDS.has(todayS.kind)) {
		out[0] = downgrade(todayS, 0.6, 'noticeable soreness — load management');
		notes.push('Noticeable soreness — hard session swapped for an easy 60% run.');
		return { sessions: out, notes };
	}

	/* Rule 2 — low energy: today's hard session becomes an easy run (70%). */
	if (j?.energy != null && j.energy <= 2 && HARD_KINDS.has(todayS.kind)) {
		out[0] = downgrade(todayS, 0.7, 'low energy check-in');
		notes.push('Energy feels low — today’s hard work becomes an easy 70% run.');
		return { sessions: out, notes };
	}

	/* Rule 3 — last workout cost more than planned: back off tomorrow. */
	if (
		ctx.last?.felt === 'hard' &&
		(ctx.last.rpe == null || ctx.last.rpe >= 8) &&
		!['quality', 'interval'].includes(ctx.last.plannedKind ?? '') &&
		tomorrowS &&
		HARD_KINDS.has(tomorrowS.kind)
	) {
		out[1] = downgrade(tomorrowS, 0.8, 'yesterday ran harder than planned');
		notes.push('Last workout felt harder than intended — tomorrow is an easy 80% run.');
		return { sessions: out, notes };
	}

	/* Rule 4 — missed yesterday: never double up. Keep today as planned. */
	if (ctx.missedYesterday) {
		notes.push('Yesterday’s session was missed — don’t chase it. Today stays as planned.');
		return { sessions: out, notes };
	}

	/* Rule 5 — poor sleep (<6 h) with a hard session today -> easy 80%. */
	if (j?.sleep_h != null && j.sleep_h < 6 && HARD_KINDS.has(todayS.kind)) {
		out[0] = downgrade(todayS, 0.8, 'poor sleep — a missed session costs less than a missed night');
		notes.push('Under 6 h sleep — today’s hard session becomes an easy 80% run.');
		return { sessions: out, notes };
	}

	return { sessions: out, notes: ['All clear — plan as scheduled.'] };
}
