import { describe, expect, it } from 'vitest';
import { matchPlan, type ActBrief } from './match';
import type { Session } from './plan';
import { addDays } from './plan';

const act = (over: Partial<ActBrief>): ActBrief => ({
	strava_id: 1,
	name: 'Morning run',
	distance: 10000,
	start_date_local: '2026-09-07T07:00:00+08:00',
	trainer: 0,
	commute: 0,
	manual: 0,
	...over
});

const sess = (over: Partial<Session>): Session => ({
	plan_date: '2026-09-07',
	kind: 'easy',
	label: 'Easy',
	distance_m: 10000,
	duration_min: null,
	pace_min_s_km: null,
	pace_max_s_km: null,
	plan_week: '2026-W37',
	reason: 'kb',
	...over
});

describe('matchPlan', () => {
	it('keys days by athlete-LOCAL date, not UTC', () => {
		// 23:30 local (+08:00) is already the NEXT day in UTC — must still match 09-07.
		const late = act({ strava_id: 1, distance: 9000, start_date_local: '2026-09-07T23:30:00+08:00' });
		const days = matchPlan([sess({ distance_m: 10000 })], [late]);
		expect(days.length).toBe(1);
		expect(days[0].planned[0].status).toBe('done'); // 9000/10000 = 0.9
	});

	it('done ≥90%, partial 50–90%, missed <50%', () => {
		const target = sess({ distance_m: 10000 });
		const mk = (d: number, id: number) => matchPlan([target], [act({ strava_id: id, distance: d })]);
		expect(mk(9000, 1)[0].planned[0].status).toBe('done');
		expect(mk(5000, 2)[0].planned[0].status).toBe('partial'); // exactly 0.5 -> partial
		expect(mk(4999, 3)[0].planned[0].status).toBe('missed');
		expect(mk(0, 4).length).toBe(1); // no qualifying run -> still a planned day
		expect(mk(0, 4)[0].planned[0].status).toBe('missed');
	});

	it('days after today stay unevaluated (planned), rest days included', () => {
		const future = sess({ plan_date: '2026-09-20', kind: 'easy', distance_m: 10000 });
		const rest = sess({ plan_date: '2026-09-21', kind: 'rest', distance_m: null });
		const days = matchPlan([future, rest], [], '2026-09-07');
		expect(days[0].planned[0].status).toBe('planned');
		expect(days[1].planned[0].status).toBe('planned');
	});

	it('today is not a failure: no run yet = planned, short run = partial', () => {
		const today = '2026-09-07';
		const none = matchPlan([sess({ plan_date: today, distance_m: 10000 })], [], today);
		expect(none[0].planned[0].status).toBe('planned'); // woke up, haven't run — never red
		const forty = matchPlan([sess({ plan_date: today, distance_m: 10000 })], [act({ strava_id: 5, distance: 4000 })], today);
		expect(forty[0].planned[0].status).toBe('partial'); // 40% today — not missed
		const full = matchPlan([sess({ plan_date: today, distance_m: 10000 })], [act({ strava_id: 6, distance: 9500 })], today);
		expect(full[0].planned[0].status).toBe('done');
	});

	it('a strictly past day with no run still surfaces as missed', () => {
		const yesterday = addDays('2026-09-07', -1);
		const days = matchPlan([sess({ plan_date: yesterday, distance_m: 10000 })], [], '2026-09-07');
		expect(days[0].planned[0].status).toBe('missed');
	});

	it('ignores trainer / commute / manual activities entirely', () => {
		const days = matchPlan([sess({ distance_m: 10000 })], [
			act({ strava_id: 1, distance: 9000, trainer: 1 }),
			act({ strava_id: 2, distance: 9000, commute: 1 }),
			act({ strava_id: 3, distance: 9000, manual: 1 })
		]);
		expect(days[0].planned[0].status).toBe('missed');
		expect(days[0].extras).toEqual([]);
	});

	it('rest day + any run = rest-flag extra', () => {
		const days = matchPlan([sess({ kind: 'rest', distance_m: null })], [act({ strava_id: 9, distance: 6000 })]);
		expect(days[0].planned[0].status).toBe('extra');
		expect(days[0].extras.length).toBe(1);
	});

	it('no distance target (no VDOT anchor): any run counts as done', () => {
		const days = matchPlan([sess({ distance_m: null })], [act({ strava_id: 1, distance: 3500 })]);
		expect(days[0].planned[0].status).toBe('done');
	});

	it('second run of the day is reported as an extra', () => {
		const days = matchPlan([sess({ distance_m: 10000 })], [
			act({ strava_id: 1, distance: 10000 }),
			act({ strava_id: 2, distance: 3000 })
		]);
		expect(days[0].planned[0].status).toBe('done');
		expect(days[0].extras.map((e) => e.strava_id)).toEqual([2]);
	});
});
