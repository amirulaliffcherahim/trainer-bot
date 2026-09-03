import { describe, expect, it } from 'vitest';
import { adjust, type AdjustCtx, type JournalState } from './s3';
import type { Session } from './plan';

const MON = '2026-09-07';
const sess = (over: Partial<Session> & { plan_date: string }): Session => ({
	kind: 'easy',
	label: 'Easy run',
	distance_m: 8000,
	duration_min: 45,
	pace_min_s_km: 400,
	pace_max_s_km: 400,
	plan_week: '2026-W37',
	reason: 'kb',
	...over
});
const today = (kind: Session['kind'], over: Partial<Session> = {}) =>
	sess({ plan_date: MON, kind, ...over });
const tomorrow = (kind: Session['kind']) => sess({ plan_date: '2026-09-08', kind });

const ctx = (over: Partial<AdjustCtx> & { journal?: JournalState | null } = {}): AdjustCtx => ({
	journal: null,
	last: null,
	missedYesterday: false,
	...over
});

describe('S3 adjustment rules', () => {
	it('sharp soreness: today becomes rest, tomorrow hard -> easy 60%', () => {
		const r = adjust([today('quality'), tomorrow('interval')], ctx({ journal: { energy: 4, sleep_h: 7, soreness: 'sharp' } }));
		expect(r.sessions[0].kind).toBe('rest');
		expect(r.sessions[0].reason).toContain('physio');
		expect(r.sessions[1].kind).toBe('easy');
		expect(r.sessions[1].distance_m).toBe(4800); // 8 km interval at 60%
		expect(r.notes.length).toBeGreaterThan(0);
	});

	it('noticeable soreness: today hard -> easy 60%', () => {
		const r = adjust([today('quality', { distance_m: 10000 })], ctx({ journal: { energy: 4, sleep_h: 7, soreness: 'noticeable' } }));
		expect(r.sessions[0].kind).toBe('easy');
		expect(r.sessions[0].distance_m).toBe(6000);
	});

	it('low energy: hard -> easy 70%', () => {
		const r = adjust([today('interval', { distance_m: 10000 })], ctx({ journal: { energy: 1, sleep_h: 7, soreness: 'none' } }));
		expect(r.sessions[0].kind).toBe('easy');
		expect(r.sessions[0].distance_m).toBe(7000);
	});

	it('easy days are untouched by soreness/energy rules', () => {
		for (const j of [{ energy: 1, sleep_h: 7, soreness: 'noticeable' } as JournalState]) {
			const r = adjust([today('easy')], ctx({ journal: j }));
			expect(r.sessions[0].kind).toBe('easy');
			expect(r.sessions[0].distance_m).toBe(8000);
		}
	});

	it('felt hard with rpe >= 8 after an easy-planned run backs off tomorrow', () => {
		const r = adjust(
			[today('easy'), tomorrow('interval')],
			ctx({ last: { date: '2026-09-06', felt: 'hard', rpe: 9, soreness: null, note: null, plannedKind: 'easy' } })
		);
		expect(r.sessions[0].kind).toBe('easy');
		expect(r.sessions[1].kind).toBe('easy'); // tomorrow downgraded
		expect(r.sessions[1].distance_m).toBeLessThan(10000);
	});

	it('missed yesterday never doubles up — today unchanged', () => {
		const r = adjust([today('quality', { distance_m: 8000 })], ctx({ missedYesterday: true }));
		expect(r.sessions[0].kind).toBe('quality');
		expect(r.sessions[0].distance_m).toBe(8000);
		expect(r.notes[0]).toContain('don’t chase');
	});

	it('under 6h sleep with hard today -> easy 80%', () => {
		const r = adjust([today('long', { distance_m: 15000 })], ctx({ journal: { energy: 4, sleep_h: 5, soreness: 'none' } }));
		expect(r.sessions[0].kind).toBe('easy');
		expect(r.sessions[0].distance_m).toBe(12000);
	});

	it('all clear: sessions untouched, friendly note', () => {
		const r = adjust([today('easy')], ctx());
		expect(r.sessions[0]).toEqual(today('easy'));
		expect(r.notes[0]).toContain('All clear');
	});
});
