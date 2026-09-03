import { predicted_time, velocity } from '../vdot';

/**
 * S2/S3 plan generator — pure & deterministic (`today` injected). Rules
 * grounded in knowledge/ files; every session carries its KB citation.
 * When the user sets explicit weekly preferences (run days, hard days) those
 * define the week structure; otherwise a legacy default template applies
 * (Mon/Tue/Thu/Fri/Sat run, Tue quality, Sat long, Wed+Sun rest).
 * Paces are seconds/km; no VDOT anchor -> pace/duration null + honest label.
 */

export interface ActRow {
	distance: number;
	start_date_local: string | null;
	trainer: number;
	commute: number;
	manual: number;
}

export interface PlanEvent {
	id?: number;
	name: string;
	distance_m: number;
	event_date: string;
	target_time_min: number | null;
	category?: string | null;
}

export type SessionKind = 'easy' | 'quality' | 'interval' | 'long' | 'rest' | 'race';

export interface Session {
	plan_date: string;
	kind: SessionKind;
	label: string;
	distance_m: number | null;
	duration_min: number | null;
	pace_min_s_km: number | null;
	pace_max_s_km: number | null;
	plan_week: string;
	reason: string;
}

/** User weekly structure. Weekdays 0=Sun .. 6=Sat. hardDays ⊆ runDays.
 *  kinds (optional): explicit per-day workout type when the user picks
 *  speed/long/tempo/easy themselves; absent days keep the default logic. */
export interface PlanPrefs {
	runDays: number[];
	hardDays: number[];
	kinds?: Partial<Record<number, SessionKind>>;
}

/** Legacy template (matches the original fixed week when prefs are absent). */
export const LEGACY_PREFS: PlanPrefs = { runDays: [1, 2, 4, 5, 6], hardDays: [2] };

/* ---------------- date helpers ---------------- */

function toDate(s: string): Date {
	const [y, m, d] = s.split('-').map(Number);
	return new Date(y, m - 1, d);
}

export function addDays(s: string, n: number): string {
	const dt = toDate(s);
	dt.setDate(dt.getDate() + n);
	const p = (x: number) => String(x).padStart(2, '0');
	return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
}

export function isoWeek(s: string): string {
	const dt = toDate(s);
	const d = new Date(Date.UTC(dt.getFullYear(), dt.getMonth(), dt.getDate()));
	const day = (d.getUTCDay() + 6) % 7;
	d.setUTCDate(d.getUTCDate() - day + 3);
	const firstThu = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
	const week =
		1 +
		Math.round(
			((d.getTime() - firstThu.getTime()) / 86400000 - 3 + ((firstThu.getUTCDay() + 6) % 7)) / 7
		);
	return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

/* ---------------- volume anchor ---------------- */

export function volumeAnchorKm(rows: ActRow[], today: string, windowDays = 28): number {
	const cutoff = addDays(today, -windowDays + 1);
	let total = 0;
	for (const r of rows) {
		if (r.trainer || r.commute || r.manual) continue;
		const date = r.start_date_local?.slice(0, 10);
		if (!date || date < cutoff) continue;
		total += r.distance / 1000;
	}
	if (total <= 0) return 18;
	return Math.max(Math.round((total / (windowDays / 7)) * 10) / 10, 5);
}

/* ---------------- pace math ---------------- */

export function secPerKm(vdotVal: number, frac: number): number {
	return (1000 / velocity(vdotVal * frac)) * 60;
}

/* ---------------- constants ---------------- */

const KB = {
	rest: 'rest_day_rules.md — full rest from running (tendon/bone lag)',
	easy: 'pacing.md / productive_training_week.md — easy & conversational; the bulk of weekly volume',
	long: 'volume_progression.md — long run ~25–30% of weekly volume, never >35%',
	quality: 'VDOT engine — threshold = 88% of VDOT, comfortably hard',
	interval: 'VDOT engine — interval = 97.5% of VDOT; I-work belongs to event build blocks only',
	taper: 'volume_progression.md — taper −3wk 75%, −2wk 55%, race week 35% easy only',
	race: 'race day — 10% underdone beats 1% overdone',
	recovery: 'post-race ~60% volume, easy only (volume_progression.md)',
	prefs: 'your chosen week: '
};

const LONG_SHARE = 0.3;
const HARD_SHARE = 0.08;

/** Effort prescription (1 = recovery … 10 = all-out) per workout kind.
 *  Ranges are the coach's target band for the session. */
export const EFFORT: Record<SessionKind, string> = {
	easy: '3–4',
	quality: '7–8', // threshold, comfortably hard
	interval: '8–9', // speedwork — hard but not all-out
	long: '4',
	rest: '1',
	race: '10'
};

export interface GenOpts {
	today: string;
	horizonDays?: number;
	vdotVal: number | null;
	anchorKm: number;
	events: PlanEvent[];
	prefs?: PlanPrefs;
}

const round50 = (m: number) => Math.round(m / 50) * 50;

type Phase = 'base' | 'build' | 'taper-3' | 'taper-2' | 'race' | 'post';

interface WeekMeta {
	targetKm: number;
	phase: Phase;
	easyOnly: boolean;
	/** weekday -> session shape for run days of that week. */
	spec: Map<number, DaySpec>;
	restDays: number[];
}

interface DaySpec {
	kind: SessionKind;
	frac: number;
	share: number;
	label: string;
	reason: string;
}

/** Build the per-week day map from prefs + phase (pure, exported for tests). */
export function buildDaySpecs(prefs: PlanPrefs, phase: Phase, isExplicit: boolean): { spec: Map<number, DaySpec>; restDays: number[] } {
	const runDays = [...prefs.runDays].sort((a, b) => a - b);
	const hardDays = [...prefs.hardDays].sort((a, b) => a - b);
	const all = new Set([0, 1, 2, 3, 4, 5, 6]);
	const restDays = [...all].filter((d) => !runDays.includes(d));
	const easyOnly = phase === 'race' || phase === 'post';
	const spec = new Map<number, DaySpec>();

	const KIND_META: Record<SessionKind, { frac: number; label: string; reason: string }> = {
		easy: { frac: 0.66, label: 'Easy run', reason: KB.easy },
		quality: { frac: 0.88, label: 'Threshold', reason: KB.quality },
		interval: { frac: 0.975, label: 'Speedwork', reason: KB.interval },
		long: { frac: 0.7, label: 'Long run', reason: KB.long },
		rest: { frac: 0, label: 'Rest', reason: KB.rest },
		race: { frac: 0, label: 'Race', reason: KB.race }
	};

	if (easyOnly) {
		const share = 1 / runDays.length;
		for (const d of runDays) {
			spec.set(d, { kind: 'easy', frac: 0.66, share, label: 'Easy run', reason: phase === 'post' ? KB.recovery : KB.taper });
		}
		return { spec, restDays };
	}

	/* user-picked per-day kinds override the default structure */
	const kinds = prefs.kinds;
	const hasKinds = !!kinds && Object.keys(kinds).length > 0;
	if (hasKinds) {
		const days = runDays.filter((d) => kinds![d]);
		const hards = days.filter((d) => kinds![d] === 'quality' || kinds![d] === 'interval');
		const longs = days.filter((d) => kinds![d] === 'long');
		const longDay = longs[0]; // at most one long day honoured
		const hardTotal = Math.min(hards.length * 0.08, 0.24);
		const longShare = longDay !== undefined ? LONG_SHARE : 0;
		const easyDays = days.filter((d) => d !== longDay && !hards.includes(d));
		const easyShare = easyDays.length > 0 ? (1 - longShare - hardTotal) / easyDays.length : 0;

		for (const d of days) {
			const chosen = kinds![d];
			if (chosen === undefined) continue; // unreachable, satisfies TS
			let kind: SessionKind = chosen;
			// taper weeks: speedwork becomes lighter threshold work
			if ((phase === 'taper-3' || phase === 'taper-2') && kind === 'interval') kind = 'quality';
			const meta = KIND_META[kind];
			const share =
				kind === 'long'
					? LONG_SHARE
					: kind === 'quality' || kind === 'interval'
						? Math.min(0.08, hardTotal / Math.max(hards.length, 1))
						: Math.max(easyShare, 0);
			if (kind === 'rest' || kind === 'race') continue;
			spec.set(d, { kind, frac: meta.frac, share, label: meta.label, reason: meta.reason });
		}
		// chosen run days without an explicit kind default to easy
		for (const d of runDays.filter((d) => !kinds![d])) {
			spec.set(d, { kind: 'easy', frac: 0.66, share: Math.max(easyShare, 0), label: 'Easy run', reason: KB.easy });
		}
		return { spec, restDays };
	}

	/* legacy default path (no per-day kinds) */
	const longCandidates = runDays.filter((d) => !hardDays.includes(d));
	const longDay = longCandidates.includes(6) ? 6 : longCandidates[longCandidates.length - 1];

	// hard-day kinds: first hard = threshold; later hards = intervals in build
	// weeks (explicit), else also threshold.
	const hards = hardDays.map((d, i) => {
		if (i === 0) {
			return { d, kind: 'quality' as SessionKind, frac: 0.88, label: 'Threshold', reason: KB.quality };
		}
		if (phase === 'build' || isExplicit === false) {
			return { d, kind: 'interval' as SessionKind, frac: 0.975, label: 'Intervals', reason: KB.interval };
		}
		return { d, kind: 'quality' as SessionKind, frac: 0.88, label: 'Threshold', reason: KB.quality };
	});

	// legacy (implicit) builds added a Thursday interval session on top
	if (!isExplicit && phase === 'build' && runDays.includes(4) && !hards.some((h) => h.d === 4)) {
		hards.push({ d: 4, kind: 'interval', frac: 0.975, label: 'Intervals', reason: KB.interval });
	}

	const hardTotal = HARD_SHARE * hards.length;
	const easyDays = runDays.filter((d) => d !== longDay && !hards.some((h) => h.d === d));
	const easyShare = easyDays.length > 0 ? (1 - LONG_SHARE - hardTotal) / easyDays.length : 0;

	for (const h of hards) {
		spec.set(h.d, { kind: h.kind, frac: h.frac, share: HARD_SHARE, label: h.label, reason: h.reason });
	}
	if (longDay !== undefined) {
		spec.set(longDay, { kind: 'long', frac: 0.7, share: LONG_SHARE, label: 'Long run', reason: KB.long });
	}
	for (const d of easyDays) {
		spec.set(d, { kind: 'easy', frac: 0.66, share: Math.max(easyShare, 0), label: 'Easy run', reason: KB.easy });
	}
	return { spec, restDays };
}

export function generatePlan(o: GenOpts): Session[] {
	const horizon = o.horizonDays ?? 14;
	const today = o.today;
	const events = o.events.filter((e) => e.event_date >= today).sort((a, b) => a.event_date.localeCompare(b.event_date));
	const event: PlanEvent | null = events[0] ?? null;
	const v = o.vdotVal;
	const prefs = o.prefs ?? LEGACY_PREFS;
	const isExplicit = o.prefs !== undefined;

	/* Pass 1 — per-ISO-week volume targets + specs. */
	const weekOrder: { wk: string; first: string }[] = [];
	{
		const seen = new Set<string>();
		for (let d = 0; d < horizon; d++) {
			const date = addDays(today, d);
			const wk = isoWeek(date);
			if (!seen.has(wk)) {
				seen.add(wk);
				weekOrder.push({ wk, first: date });
			}
		}
	}

	const metaByWeek = new Map<string, WeekMeta>();
	let prevTarget = o.anchorKm;
	for (let i = 0; i < weekOrder.length; i++) {
		const { wk, first } = weekOrder[i];
		const dayMs = toDate(first).getTime();
		let phase: Phase = 'base';
		let target = prevTarget;

		if (event) {
			const eventMs = toDate(event.event_date).getTime();
			const daysTo = Math.ceil((eventMs - dayMs) / 86400000);
			if (daysTo < 0) {
				phase = 'post';
				target = Math.max(prevTarget * 0.6, 8);
			} else if (daysTo <= 6) {
				phase = 'race';
				target = Math.max(prevTarget * 0.35, 8);
			} else if (daysTo <= 13) {
				phase = 'taper-2';
				target = prevTarget * 0.55;
			} else if (daysTo <= 20) {
				phase = 'taper-3';
				target = prevTarget * 0.75;
			} else {
				phase = 'build';
				target = prevTarget * 1.1;
			}
		} else if (weekOrder.length >= 3 && i % 3 === 2) {
			phase = 'base'; // step-back week
			target = Math.max(prevTarget * 0.65, 8);
		} else {
			target = Math.min(prevTarget * 1.1, prevTarget + 4);
		}
		target = Math.round(target * 10) / 10;

		const { spec, restDays } = buildDaySpecs(prefs, phase, isExplicit);
		const easyOnly = phase === 'race' || phase === 'post';
		metaByWeek.set(wk, { targetKm: target, phase, easyOnly, spec, restDays });
		prevTarget = target;
	}

	/* Pass 2 — build sessions day by day. */
	const out: Session[] = [];
	for (let d = 0; d < horizon; d++) {
		const date = addDays(today, d);
		const wk = isoWeek(date);
		const meta = metaByWeek.get(wk)!;
		const wd = toDate(date).getDay();

		if (event && date === event.event_date) {
			const goalMin = event.target_time_min ?? (v ? predicted_time(v, event.distance_m) : null);
			const pace = goalMin !== null ? (goalMin * 60) / (event.distance_m / 1000) : null;
			out.push({
				plan_date: date,
				kind: 'race',
				label: event.category || event.name,
				distance_m: event.distance_m,
				duration_min: goalMin !== null ? Math.round(goalMin * 10) / 10 : null,
				pace_min_s_km: pace !== null ? Math.round(pace) : null,
				pace_max_s_km: pace !== null ? Math.round(pace) : null,
				plan_week: wk,
				reason: KB.race
			});
			continue;
		}

		const ds = meta.spec.get(wd);
		if (!ds) {
			// not a run day -> rest (or Wed/Sun rest under the legacy template)
			out.push({
				plan_date: date,
				kind: 'rest',
				label: 'Rest',
				distance_m: null,
				duration_min: null,
				pace_min_s_km: null,
				pace_max_s_km: null,
				plan_week: wk,
				reason: isExplicit ? KB.prefs + 'not a training day' : KB.rest
			});
			continue;
		}

		const distM = Math.max(round50(meta.targetKm * ds.share * 1000), 0);
		// Workouts are prescribed by EFFORT (1 = recovery, 10 = all-out), not
		// pace. VDOT stays the fitness anchor and drives Fitness/Race screens.
		const label = `${ds.label} · effort ${EFFORT[ds.kind]}/10`;
		out.push({
			plan_date: date,
			kind: ds.kind,
			label,
			distance_m: distM > 0 ? distM : null,
			duration_min: null,
			pace_min_s_km: null,
			pace_max_s_km: null,
			plan_week: wk,
			reason: ds.reason
		});
	}
	return out;
}

export function fmtPace(sPerKm: number): string {
	const s = Math.round(sPerKm);
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
