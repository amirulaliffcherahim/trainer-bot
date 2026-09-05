import { describe, expect, it } from 'vitest';
import { raceBriefing } from './race';
import type { PlanEvent } from './plan';

const HM: PlanEvent = { name: 'HM Test', distance_m: 21097.5, event_date: '2026-11-15', target_time_min: null };

describe('race briefing', () => {
	it('predicts goal time/pace from VDOT when no target is set', () => {
		const b = raceBriefing(HM, 50);
		expect(b.goal.fromTarget).toBe(false);
		expect(b.goal.timeMin).toBeGreaterThan(80); // HM at VDOT 50 ≈ 1:31
		expect(b.goal.timeMin).toBeLessThan(100);
		// pace in s/km should equal goal min converted
		expect(b.goal.pace_s_km).toBeCloseTo((b.goal.timeMin * 60) / 21.0975, 1);
	});

	it('uses the explicit target when provided', () => {
		const b = raceBriefing({ ...HM, target_time_min: 120 }, 50);
		expect(b.goal.fromTarget).toBe(true);
		expect(b.goal.timeMin).toBe(120);
	});

	it('taper table shows only the weeks still ahead', () => {
		const base = '2026-09-05';
		const in10 = { ...HM, event_date: '2026-09-13' }; // 8 days out from base
		const b10 = raceBriefing(in10, 50, base);
		expect(b10.taper.map((t) => t.out).sort()).toEqual([1, 2]);
		const in40 = { ...HM, event_date: '2026-10-13' }; // 38 days out from base
		const b40 = raceBriefing(in40, 50, base);
		expect(b40.taper.map((t) => t.out)).toEqual([3, 2, 1]);
	});

	it('race week row is easy-only; negative-split and fuel guidance present', () => {
		const b = raceBriefing(HM, 50);
		expect(b.taper.find((t) => t.out === 1)?.easyOnly).toBe(true);
		expect(b.negativeSplit.some((l) => l.includes('5–10 s/km slower'))).toBe(true);
		expect(b.fueling.some((l) => l.includes('sodium'))).toBe(true);
		expect(b.fueling.some((l) => l.includes('20–24 g protein'))).toBe(true);
		expect(b.postRace.some((l) => l.includes('VO₂ estimate'))).toBe(true);
	});
});
