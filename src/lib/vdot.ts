/**
 * VDOT engine — TypeScript port of vdoto2.com's algorithm.
 * Source of truth: knowledge/vdot_engine/vdot_calculator_research.md
 * (decoded from the site's shipped JS). Units: distance meters, time minutes,
 * speed m/min, VO2 ml/kg/min. Values validated against the engine's own
 * outputs — see vdot.test.ts anchors.
 */

/** Aerobic demand of running at v m/min (ml/kg/min). */
export function vo2_demand(v: number): number {
	return 0.182258 * v + 0.000104 * v * v - 4.6;
}

/** Fraction of VO2max holdable for t minutes (race-effort curve). */
export function frac(t: number): number {
	return (
		0.8 +
		0.298956 * Math.exp(-0.193261 * t) +
		0.189439 * Math.exp(-0.012778 * t)
	);
}

/** Normalize sub-1200 m race speeds toward 1600 m (anaerobic share). */
export function speed_param(d: number, t: number): number {
	if (d >= 1200) return d / t;
	if (d > 800) {
		const i = 1600 / d;
		const r = (1600 - d) / 800;
		return 1600 / (t * (i + 0.1 * r));
	}
	return 1600 / (t * (800 / d) * 2.1);
}

/** VDOT from a race/effort: d meters, t minutes. */
export function vdot(d: number, t: number): number {
	return vo2_demand(speed_param(d, t)) / frac(t);
}

/** Inverse demand curve: effort x (ml/kg/min) -> velocity (m/min). */
export function velocity(x: number): number {
	return 29.54 + 5.000663 * x - 0.007546 * x * x;
}

/** Predicted race time (minutes) for distance d at VDOT v (Newton x3). */
export function predicted_time(v: number, d: number): number {
	let i = d / (4 * v);
	for (let k = 0; k < 3; k++) {
		const e = Math.exp(-0.193261 * i);
		const r = 0.298956 * e + Math.exp(-0.012778 * i) * 0.189439 + 0.8;
		const o = (v * r) ** 2 * -0.0075 + v * r * 5.000663 + 29.54;
		const c = 0.298956 * e * 0.19326;
		const s = c - Math.exp(-0.012778 * i) * 0.189439 * -0.012778;
		const l = r * s * v * -0.007546 * 3;
		const a = s * v * 5.000663 + l;
		i -= (i - d / o) / (d * a / (o * o) + 1);
	}
	const h = d / i; // converged velocity (m/min)
	const u = d / h; // time (min)
	if (d >= 1200) return u;
	return u / (h / speed_param(d, u)); // sub-1200 m rescale
}

/** Pace (min per unit distance d_unit meters) for effort multiplier m. */
export function effort_pace(v: number, d_unit: number, m: number): number {
	return d_unit / velocity(v * m);
}

/* Training pace multipliers (engine constants). */
export const PACE = {
	easy_slow: 0.7,
	easy_fast: 0.62,
	threshold: 0.88,
	interval: 0.975
} as const;

/** Slow-VDOT beginner substitution (engine: v < 39 -> v*2/3+13). */
export const SLOW_VDOT_LIMIT = 39;
export function sr_vdot(v: number): number {
	return (v * 2) / 3 + 13;
}

/**
 * Per-400m offsets for Rep / Fast-Reps vs Interval pace (seconds).
 * Rep = I - 6s per 400m; FastReps = R - 4s per 200m.
 */
export function rep_pace_min(v: number, d_unit: number): number {
	return effort_pace(v, d_unit, PACE.interval) - (d_unit / 400) * (6 / 60);
}
export function fast_reps_pace_min(v: number, d_unit: number): number {
	return rep_pace_min(v, d_unit) - (d_unit / 200) * (4 / 60);
}

export interface VdotResult {
	vdot: number;
	/** Training paces, min per 1609.344 m (per mile). */
	paces: {
		easy: { slow: number; fast: number };
		marathon: number;
		threshold: number;
		interval: number;
		repetition: number;
		fast_reps: number;
	};
	/** Equivalent race times in minutes, keyed by distance in meters. */
	equivalents: Record<string, number>;
}

/** Full derived table for one VDOT (marathon pace solved at 42195 m). */
export function build_result(v: number): VdotResult {
	const mile = 1609.344;
	const isSlow = v < SLOW_VDOT_LIMIT;
	const sr = sr_vdot(v);
	// Engine: easy/interval/reps substitute SRVDOT when slow; threshold uses
	// the midpoint (SR+orig)/2; marathon is NOT substituted.
	const effort = (fn: (vv: number) => number, use: 'sr' | 'mid' | 'orig'): number =>
		fn(isSlow ? (use === 'sr' ? sr : use === 'mid' ? (sr + v) / 2 : v) : v);
	return {
		vdot: v,
		paces: {
			easy: {
				slow: effort((vv) => effort_pace(vv, mile, PACE.easy_slow), 'sr'),
				fast: effort((vv) => effort_pace(vv, mile, PACE.easy_fast), 'sr')
			},
			marathon: (predicted_time(v, 42195) * mile) / 42195,
			threshold: effort((vv) => effort_pace(vv, mile, PACE.threshold), 'mid'),
			interval: effort((vv) => effort_pace(vv, mile, PACE.interval), 'sr'),
			repetition: effort((vv) => rep_pace_min(vv, mile), 'sr'),
			fast_reps: effort((vv) => fast_reps_pace_min(vv, mile), 'sr')
		},
		equivalents: {
			marathon: predicted_time(v, 42195),
			half: predicted_time(v, 21097.5),
			'15k': predicted_time(v, 15000),
			'10k': predicted_time(v, 10000),
			'5k': predicted_time(v, 5000),
			mile: predicted_time(v, mile)
		}
	};
}

/** Format minutes -> canonical "h:mm:ss" (hour zero-padded: 00:19:56). */
export function fmt_time(min: number): string {
	const s = Math.round(min * 60);
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const ss = s % 60;
	return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}

/** Format minutes-per-mile -> "m:ss/mi" style string (mm:ss). */
export function fmt_pace(min: number): string {
	const s = Math.round(min * 60);
	const m = Math.floor(s / 60);
	const sec = s % 60;
	return `${m}:${String(sec).padStart(2, '0')}`;
}
