import { predicted_time } from '../vdot';
import type { PlanEvent } from './plan';

/**
 * S4 — race-day briefing. Pure & deterministic; every text block cites its
 * knowledge/ source. Fed by the active goal event + current VDOT.
 */

export interface TaperRow {
	out: number; // weeks out from the race
	pct: number; // target volume %
	easyOnly: boolean;
}

export interface RaceBriefing {
	race: PlanEvent;
	daysTo: number;
	goal: {
		timeMin: number;
		pace_s_km: number;
		fromTarget: boolean;
	};
	negativeSplit: string[];
	fueling: string[];
	taper: TaperRow[];
	postRace: string[];
}

const fmtTime = (min: number) => {
	const s = Math.round(min * 60);
	return `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};

const fmtPace = (sPerKm: number) => {
	const s = Math.round(sPerKm);
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

export function raceBriefing(event: PlanEvent, vdotVal: number | null): RaceBriefing {
	const now = new Date();
	now.setHours(0, 0, 0, 0);
	const daysTo = Math.max(0, Math.round((new Date(event.event_date + 'T00:00:00').getTime() - now.getTime()) / 86400000));
	const fromTarget = event.target_time_min != null && event.target_time_min > 0;
	const goalMin = fromTarget
		? (event.target_time_min as number)
		: vdotVal
			? predicted_time(vdotVal, event.distance_m)
			: (event.distance_m / 1000) * 6; // no anchor: naive 6:00/km placeholder, flagged below
	const pace = (goalMin * 60) / (event.distance_m / 1000);

	const weeksOut = Math.ceil(daysTo / 7);
	const taperRows: TaperRow[] = [];
	for (const [out, pct, easy] of [
		[3, 75, false],
		[2, 55, false],
		[1, 35, true]
	] as const) {
		if (out <= weeksOut) taperRows.push({ out, pct, easyOnly: easy });
	}

	const kmLabel = event.distance_m >= 1000 ? `${Math.round((event.distance_m / 1000) * 10) / 10} km` : `${Math.round(event.distance_m)} m`;

	const negativeSplit = [
		`Goal ${kmLabel} in ${fmtTime(goalMin)} → race pace ${fmtPace(pace)}/km${fromTarget ? '' : vdotVal ? ' (est. VO₂ max-predicted — update it after your next effort/race)' : ' (no VO₂ estimate yet — placeholder pace, sync some runs first)'}.`,
		'Run the FIRST HALF 5–10 s/km slower than goal pace; the race is lost in the first 3 km far more often than the last 3. (pacing.md)',
		'Walk through aid stations: ~10 s walking costs ~40 m — cheaper than the energy cost of pushing. (pacing.md)'
	];

	const fueling = [
		'Night before: good carbs — wholewheat pasta, brown rice, sweet potato. (productive_training_week.md)',
		'Pre-race: eat 1–3 h out; for efforts over ~2–3 h take on 200–300 g carbohydrate in the 1–4 h before. (endurance_nutrition_daily.md)',
		'Pre-hydrate: 400–600 ml in the 2 h before the race. (heat_humidity.md)',
		'During (60+ min): ~500–750 ml/h in the heat and electrolytes/sodium — plain water alone dilutes salt. (heat_humidity.md)',
		'Post: 20–24 g protein within 30 min, then a bigger meal about an hour later; 1–1.2 g/kg carbs + 10–25 g protein in the recovery window. (productive_training_week.md / endurance_nutrition_daily.md)'
	];

	const postRace = [
		'The finish becomes your freshest VO₂ estimate automatically on the next sync — no data entry.',
		'Week after: ~60% volume, easy only (the engine already schedules it if you renew after race day). (volume_progression.md)',
		'Rest-day rules still apply: Wed + Sun full rest, mobility + 10-min routine on rest days. (rest_day_rules.md)',
		'After a long race, do the 4-min post-run flush and daily mobility rather than jumping back to quality. (mobility KB)'
	];

	return {
		race: event,
		daysTo,
		goal: { timeMin: goalMin, pace_s_km: pace, fromTarget },
		negativeSplit,
		fueling,
		taper: taperRows,
		postRace
	};
}
