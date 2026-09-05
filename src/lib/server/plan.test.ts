import { describe, expect, it } from 'vitest';
import { addDays, generatePlan, isoWeek, planHorizon, volumeAnchorKm, type ActRow, type PlanEvent } from './plan';

// 2026-09-07 is a Monday (athlete's rest rule: Wed + Sun rest).
const MON = '2026-09-07';

function opts(over: Partial<{ anchorKm: number; vdotVal: number | null; events: PlanEvent[]; horizonDays: number; prefs: import('./plan').PlanPrefs }> = {}) {
	return {
		today: MON,
		anchorKm: over.anchorKm ?? 30,
		vdotVal: over.vdotVal === undefined ? 50 : over.vdotVal,
		events: over.events ?? [],
		horizonDays: over.horizonDays ?? 14,
		...(over.prefs ? { prefs: over.prefs } : {})
	};
}

describe('volumeAnchorKm', () => {
	it('falls back to the KB floor (18 km/wk) with no data', () => {
		expect(volumeAnchorKm([], MON)).toBe(18);
	});

	it('averages run km over the window and ignores trainer/commute/manual', () => {
		const rows: ActRow[] = [
			{ distance: 10000, start_date_local: MON + 'T07:00:00+08:00', trainer: 0, commute: 0, manual: 0 },
			{ distance: 5000, start_date_local: addDays(MON, -7) + 'T07:00:00+08:00', trainer: 0, commute: 0, manual: 0 },
			{ distance: 90000, start_date_local: addDays(MON, -1) + 'T07:00:00+08:00', trainer: 1, commute: 0, manual: 0 }
		];
		// 15 km of qualifying runs over 4 weeks = 3.75 km/wk -> floor at 5
		expect(volumeAnchorKm(rows, MON)).toBe(5);
	});
});

describe('base-mode plan (no event)', () => {
	const s = generatePlan(opts());

	it('rest days on Wed + Sun every week (rest_day_rules.md)', () => {
		for (const wk of [...new Set(s.map((x) => x.plan_week))]) {
			const restDates = s.filter((x) => x.plan_week === wk && x.kind === 'rest').map((x) => x.plan_date);
			expect(restDates.length).toBe(2);
			for (const d of restDates) {
				const wd = new Date(d + 'T00:00:00').getDay();
				expect([0, 3]).toContain(wd); // Sun / Wed
			}
		}
	});

	it('long run lands Saturday at ~30% of week volume', () => {
		const long = s.filter((x) => x.kind === 'long');
		expect(long.length).toBe(2); // two Saturdays in 14 days
		for (const l of long) {
			const wk = l.plan_week;
			const wkVol = s.filter((x) => x.plan_week === wk && x.distance_m).reduce((a, x) => a + (x.distance_m ?? 0), 0);
			expect((l.distance_m ?? 0) / wkVol).toBeGreaterThan(0.25);
			expect((l.distance_m ?? 0) / wkVol).toBeLessThanOrEqual(0.35);
		}
	});

	it('workouts carry effort targets (1–10), never paces', () => {
		const wv = generatePlan(opts());
		const runs = wv.filter((x) => x.kind !== 'rest' && x.kind !== 'race');
		expect(runs.length).toBeGreaterThan(0);
		for (const r of runs) {
			expect(r.label).toMatch(/effort (\d+)(–\d+)?\/10/);
			expect(r.label).not.toContain('/km');
			expect(r.pace_min_s_km).toBeNull();
		}
	});

	it('step-back week every 3rd week (~65% volume)', () => {
		const three = generatePlan(opts({ horizonDays: 21, anchorKm: 50 }));
		const totals: number[] = [];
		for (const wk of [...new Set(three.map((x) => x.plan_week))]) {
			totals.push(three.filter((x) => x.plan_week === wk && x.kind !== 'rest').reduce((a, x) => a + (x.distance_m ?? 0), 0));
		}
		expect(totals.length).toBe(3);
		// week3 target = week2 * 0.65; allow rounding on per-day distribution
		expect(totals[2] / totals[1]).toBeLessThan(0.7);
		expect(totals[2] / totals[1]).toBeGreaterThan(0.6);
	});

	it('week-over-week growth never exceeds ~10% between non-step-back weeks', () => {
		const two = generatePlan(opts({ horizonDays: 14, anchorKm: 40 }));
		const totals = [...new Set(two.map((x) => x.plan_week))].map((wk) =>
			two.filter((x) => x.plan_week === wk && x.kind !== 'rest').reduce((a, x) => a + (x.distance_m ?? 0), 0)
		);
		expect(totals[1] / totals[0]).toBeLessThanOrEqual(1.1);
	});
});

describe('planHorizon (month unless a race runs)', () => {
	it('no event -> current calendar month end, race-off', () => {
		expect(planHorizon('2026-02-01', [])).toEqual({ to: '2026-02-28', isRace: false, name: null, daysTo: 28 });
	});

	it('late in the month stays inside the month', () => {
		expect(planHorizon('2026-09-30', [])).toEqual({ to: '2026-09-30', isRace: false, name: null, daysTo: 1 });
	});

	it('leap February is respected', () => {
		expect(planHorizon('2028-02-15', []).to).toBe('2028-02-29');
	});

	it('an upcoming race extends the horizon past month end', () => {
		const h = planHorizon('2026-09-30', [{ name: 'HM', distance_m: 21097.5, event_date: '2026-10-25', target_time_min: null }]);
		expect(h).toMatchObject({ to: '2026-10-25', isRace: true, name: 'HM', daysTo: 26 });
	});
});

describe('race-anchored build keeps step-back weeks', () => {
	it('a ~5-week build dips to ~65% on the third week (volume_progression.md)', () => {
		const ev: PlanEvent = { name: 'HM', distance_m: 21097.5, event_date: addDays(MON, 40), target_time_min: null };
		const p = generatePlan(opts({ events: [ev], horizonDays: 35, anchorKm: 40 }));
		const totals = [...new Set(p.map((x) => x.plan_week))]
			.slice(0, 5)
			.map((wk) => p.filter((x) => x.plan_week === wk && x.kind !== 'rest').reduce((a, x) => a + (x.distance_m ?? 0), 0));
		expect(totals.length).toBe(5);
		expect(totals[2] / totals[1]).toBeGreaterThan(0.6);
		expect(totals[2] / totals[1]).toBeLessThan(0.7); // step-back week
	});
});

describe('post-race weeks survive a Renew', () => {
	it('the week right after a race is easy-only ~60%; later weeks resume progression', () => {
		const racePast: PlanEvent = { name: '10K', distance_m: 10000, event_date: addDays(MON, -1), target_time_min: null };
		const p = generatePlan(opts({ events: [racePast], horizonDays: 21, anchorKm: 40 }));
		const week1 = p.filter((x) => x.plan_week === isoWeek(MON));
		const runs1 = week1.filter((x) => x.kind !== 'rest');
		expect(runs1.length).toBeGreaterThan(0);
		expect(runs1.every((x) => x.kind === 'easy')).toBe(true); // recovery week
		// a later week brings back quality work (base resumed, not all-post)
		expect(p.some((x) => x.kind === 'quality')).toBe(true);
	});
});

describe('event-aware plan', () => {
	const event: PlanEvent = { name: 'HM Test', distance_m: 21097.5, event_date: addDays(MON, 6), target_time_min: null };
	// race week = daysTo <= 6 from week start => this event lands in the race week
	const s = generatePlan(opts({ events: [event], horizonDays: 7 }));

	it('race week is easy-only (taper rule)', () => {
		const kinds = s.filter((x) => x.kind !== 'rest' && x.kind !== 'race').map((x) => x.kind);
		expect(kinds.every((k) => k === 'easy')).toBe(true);
	});

	it('race-day session matches the event with a VDOT-predicted target', () => {
		const race = s.find((x) => x.kind === 'race');
		expect(race).toBeDefined();
		expect(race!.plan_date).toBe(event.event_date);
		expect(race!.distance_m).toBe(21097.5);
		expect(race!.duration_min).not.toBeNull(); // predicted from VDOT 50
		expect(race!.duration_min!).toBeGreaterThan(80); // HM at VDOT 50 ≈ 1:31
		expect(race!.duration_min!).toBeLessThan(100);
	});
});

describe('interval sessions in build weeks', () => {
	it('no intervals in base mode or taper weeks', () => {
		const base = generatePlan(opts());
		expect(base.some((x) => x.kind === 'interval')).toBe(false);
		const taper = generatePlan(opts({ events: [{ name: 'E', distance_m: 21097.5, event_date: addDays(MON, 10), target_time_min: null }], horizonDays: 14 }));
		expect(taper.some((x) => x.kind === 'interval')).toBe(false);
	});

	it('build weeks schedule one interval session on Thursday at 97.5% of VDOT', () => {
		// event far enough out that the first week is a build week
		const ev: PlanEvent = { name: 'HM', distance_m: 21097.5, event_date: addDays(MON, 40), target_time_min: null };
		const build = generatePlan(opts({ events: [ev], horizonDays: 7 }));
		const iv = build.filter((x) => x.kind === 'interval');
		expect(iv.length).toBe(1);
		const d = new Date(iv[0].plan_date + 'T00:00:00').getDay();
		expect(d).toBe(4); // Thursday
		// effort-based: label carries an 8–9/10 speedwork target, no pace
		expect(iv[0].label).toContain('effort');
		expect(iv[0].pace_min_s_km).toBeNull();
		expect(iv[0].reason).toContain('97.5%');
	});
});

describe('date helpers', () => {
	it('isoWeek matches the 2026-09-07 week (W37)', () => {
		expect(isoWeek(MON)).toBe('2026-W37');
	});
	it('addDays crosses month boundaries', () => {
		expect(addDays('2026-09-30', 2)).toBe('2026-10-02');
	});
});

describe('per-day kinds (user picks speed/long/tempo/easy)', () => {
	it('honours an explicit Speedwork day even in base mode', () => {
		const s = generatePlan(opts({ prefs: { runDays: [1, 2, 4, 5, 6], hardDays: [2, 4], kinds: { 1: 'easy', 2: 'interval', 4: 'easy', 5: 'easy', 6: 'long' } } }));
		const speedDays = s.filter((x) => x.kind === 'interval');
		expect(speedDays.length).toBe(2); // Tuesday each week
		expect(speedDays[0].reason).toContain('97.5%');
	});

	it('taper weeks downgrade chosen speedwork to threshold', () => {
		const s = generatePlan(
			opts({
				events: [{ name: 'E', distance_m: 21097.5, event_date: addDays(MON, 12), target_time_min: null }], // taper-2
				horizonDays: 14,
				prefs: { runDays: [1, 2, 4, 5, 6], hardDays: [2, 4], kinds: { 1: 'easy', 2: 'interval', 4: 'easy', 5: 'easy', 6: 'long' } }
			})
		);
		expect(s.some((x) => x.kind === 'interval')).toBe(false);
		expect(s.some((x) => x.kind === 'quality')).toBe(true);
	});

	it('kinds days missing from the map default to easy', () => {
		const s = generatePlan(opts({ prefs: { runDays: [1, 2, 4, 5, 6], hardDays: [2], kinds: { 2: 'quality' } } }));
		// Monday has no kind -> easy
		expect(s.find((x) => x.plan_date === MON)?.kind).toBe('easy');
	});
});
