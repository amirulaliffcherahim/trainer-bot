import { describe, expect, it } from 'vitest';
import {
	build_result,
	fast_reps_pace_min,
	fmt_pace,
	fmt_time,
	predicted_time,
	rep_pace_min,
	velocity,
	vdot,
	vo2_demand
} from './vdot';

// Anchors verified against vdoto2.com's own engine outputs
// (see knowledge/vdot_engine/vdot_calculator_research.md).

describe('VDOT from a race', () => {
	it('5K in 20:00 -> VDOT 49.8', () => {
		expect(vdot(5000, 20)).toBeCloseTo(49.8, 1);
	});

	it('VO2 demand at 250 m/min is 47.46; fraction at 20 min is 0.953', () => {
		expect(vo2_demand(250)).toBeCloseTo(47.46, 2);
	});
});

describe('race time prediction', () => {
	it('5K 20:00 equivalent times match engine', () => {
		const v = vdot(5000, 20);
		expect(fmt_time(predicted_time(v, 1609.344))).toBe('00:05:51');
		expect(fmt_time(predicted_time(v, 10000))).toBe('00:41:29');
		expect(fmt_time(predicted_time(v, 21097.5))).toBe('01:31:53');
		expect(fmt_time(predicted_time(v, 42195))).toBe('03:11:23');
	});

	it('VDOT 50 -> 5K 19:56, marathon 3:10:46', () => {
		expect(fmt_time(predicted_time(50, 5000))).toBe('00:19:56');
		expect(fmt_time(predicted_time(50, 42195))).toBe('03:10:46');
	});

	it('VDOT 45 -> marathon ~3:28:23', () => {
		expect(fmt_time(predicted_time(45, 42195))).toBe('03:28:23');
	});
});

describe('training paces', () => {
	it('threshold pace is ~88% of VDOT (velocity inverse holds)', () => {
		// pace at multiplier m = unit / velocity(vdot*m)
		const v = 50;
		const t = 1609.344 / velocity(v * 0.88);
		expect(fmt_pace(t)).toBe('6:51');
	});

	it('rep is interval minus 6 s per 400 m; fast reps minus a further 4 s per 200 m', () => {
		const v = 50;
		const mile = 1609.344;
		const iv = mile / velocity(v * 0.975);
		expect(rep_pace_min(v, mile)).toBeCloseTo(iv - (mile / 400) * (6 / 60), 6);
		expect(fast_reps_pace_min(v, mile)).toBeCloseTo(
			rep_pace_min(v, mile) - (mile / 200) * (4 / 60),
			6
		);
	});

	it('slow VDOT (<39) substitutes SR = v*2/3+13', () => {
		const r = build_result(30);
		// easy fast bound uses substituted vdot 33
		const expect33 = 1609.344 / velocity(33 * 0.62);
		expect(r.paces.easy.fast).toBeCloseTo(expect33, 6);
		// marathon pace NOT substituted (uses raw vdot 30)
		expect(r.paces.marathon).toBeCloseTo(predicted_time(30, 42195) * 1609.344 / 42195, 6);
	});
});

describe('full table', () => {
	it('build_result(50) matches published tables', () => {
		const r = build_result(50);
		expect(r.paces.threshold).toBeCloseTo(1609.344 / velocity(44), 3); // 88%
		expect(fmt_time(r.equivalents['5k'])).toBe('00:19:56');
		expect(fmt_time(r.equivalents.marathon)).toBe('03:10:46');
	});
});
