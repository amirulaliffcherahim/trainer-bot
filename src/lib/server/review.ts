import type { ActivityRow } from './plan_store';
import { secPerKm } from './plan';

/**
 * Rule-based "AI" review of an activity (the AI talks, the code does the
 * math). Zones come from the VDOT pace bands; copy is template-driven.
 */

export interface Review {
	zone: 'easy' | 'long' | 'threshold' | 'interval' | 'above' | 'slow' | 'no-anchor' | 'other-sport';
	headline: string;
	points: string[];
}

const fmt = (sPerKm: number) => {
	const s = Math.round(sPerKm);
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

export function classifyPace(vdotVal: number, paceS: number): Review['zone'] {
	// boundaries from the VDOT curve (seconds/km, bigger = slower)
	const bSlow = secPerKm(vdotVal, 0.62); // easy, slower side
	const bFast = secPerKm(vdotVal, 0.7); // easy, faster side
	const t = secPerKm(vdotVal, 0.88); // threshold
	const iv = secPerKm(vdotVal, 0.975); // interval
	if (paceS > bSlow + 20) return 'slow';
	if (paceS > t + 12) return 'easy'; // easy band + long-run pace
	if (paceS > (iv + t) / 2) return 'threshold'; // ~t ± 12s
	if (paceS > iv - 10) return 'interval';
	return 'above';
}

export function reviewActivity(a: ActivityRow, vdotVal: number | null): Review {
	const isRun = /run/i.test(a.sport_type ?? a.type ?? '') || !a.type;
	const distKm = a.distance / 1000;
	const paceS = a.moving_time > 0 ? a.moving_time / distKm : null;

	if (!isRun) {
		return {
			zone: 'other-sport',
			headline: `${a.sport_type ?? a.type ?? 'Activity'} — logged, not scored as a run`,
			points: ['Review engine scores running sessions; other sports still count toward load.']
		};
	}
	if (paceS === null || a.distance < 800) {
		return { zone: 'no-anchor', headline: 'Too short to score', points: ['Sessions under 800 m don\'t feed the VDOT scan.'] };
	}
	if (!vdotVal) {
		return {
			zone: 'no-anchor',
			headline: 'No VO₂ estimate yet',
			points: [`${distKm.toFixed(1)} km at ${fmt(paceS)}/km logged.`, 'Sync enough runs and I\'ll score effort against your zones.']
		};
	}

	const zone = classifyPace(vdotVal, paceS);
	const lines: string[] = [];
	const header = `${distKm.toFixed(1)} km in ${fmt(paceS)}/km`;
	const hr = a.average_heartrate ? ` · avg HR ${Math.round(a.average_heartrate)} bpm` : '';

	switch (zone) {
		case 'easy':
			lines.push(`${header}${hr} — sits in your Easy zone. This is where 75–80% of your week should live.`);
			break;
		case 'slow':
			lines.push(`${header}${hr} — slower than your Easy band. Fine for recovery/heat days; note it in feedback if it was a hard effort in bad conditions.`);
			break;
		case 'threshold':
			lines.push(`${header}${hr} — right at Threshold. Comfortably hard, short-sentence pace. Good quality session.`);
			break;
		case 'interval':
			lines.push(`${header}${hr} — Interval zone (≈97.5% of VO₂ max). Keep these 3–5 min reps with full jogs — past 5 min you drift anaerobic.`);
			break;
		case 'above':
			lines.push(`${header}${hr} — faster than Interval pace. Short rep territory; fine for strides/reps with long recovery, risky as a habit.`);
			break;
		default:
			break;
	}
	lines.push(a.average_heartrate && a.average_heartrate > 0 ? 'Effort check: was the feel as hard as the number? Log it below.' : 'Log how it felt below — feel + numbers together steer tomorrow.');
	return { zone, headline: `${header}${hr}`, points: lines };
}
