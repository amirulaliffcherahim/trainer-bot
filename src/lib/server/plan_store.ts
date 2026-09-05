import { dbAll, dbGet, dbRun, dbExec } from './db';
import type { ActRow, PlanEvent, PlanPrefs, Session } from './plan';
import { generatePlan, volumeAnchorKm, addDays, planHorizon, EFFORT } from './plan';
import { latestSnapshot } from './fitness';
import { matchPlan, type ActBrief } from './match';
import { adjust, type AdjustCtx, type JournalState } from './s3';

/** YYYY-MM-DD in the server's local timezone (single-user: same as athlete). */
export function todayLocal(): string {
	const d = new Date();
	const p = (x: number) => String(x).padStart(2, '0');
	return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/* ---------------- plan preferences ---------------- */

export async function loadPrefs(): Promise<PlanPrefs | null> {
	const row = await dbGet<{ run_days: string; hard_days: string; kinds: string | null }>(
		'SELECT run_days, hard_days, kinds FROM plan_prefs WHERE id = 1'
	);
	if (!row) return null;
	try {
		const kindsRaw = row.kinds ? JSON.parse(row.kinds) : null;
		return {
			runDays: JSON.parse(row.run_days) as number[],
			hardDays: JSON.parse(row.hard_days) as number[],
			...(kindsRaw ? { kinds: kindsRaw as PlanPrefs['kinds'] } : {})
		};
	} catch {
		return null;
	}
}

export async function savePrefs(p: PlanPrefs): Promise<void> {
	const valid = p.runDays.filter((d) => Number.isInteger(d) && d >= 0 && d <= 6);
	const kinds = p.kinds && Object.keys(p.kinds).length > 0 ? p.kinds : null;
	const hard = kinds
		? valid.filter((d) => kinds[d] === 'quality' || kinds[d] === 'interval')
		: [...new Set(p.hardDays.filter((d) => valid.includes(d)))].sort((a, b) => a - b);
	if (valid.length < 2) throw new Error('pick at least 2 training days');
	await dbRun(
		`INSERT INTO plan_prefs (id, run_days, hard_days, kinds, updated_at)
		 VALUES (1, ?, ?, ?, ?)
		 ON CONFLICT(id) DO UPDATE SET run_days=excluded.run_days, hard_days=excluded.hard_days, kinds=excluded.kinds, updated_at=excluded.updated_at`,
		[
			JSON.stringify(valid.sort((a, b) => a - b)),
			JSON.stringify(hard),
			kinds ? JSON.stringify(kinds) : null,
			Math.floor(Date.now() / 1000)
		]
	);
}

/* ---------------- events ---------------- */

export async function listEvents(): Promise<PlanEvent[]> {
	return dbAll<PlanEvent>('SELECT id, name, distance_m, event_date, target_time_min, category FROM events ORDER BY event_date');
}

export async function addEvent(e: {
	name: string;
	distance_m: number;
	event_date: string;
	target_time_min: number | null;
	category?: string | null;
}): Promise<PlanEvent> {
	if (!e.name.trim()) throw new Error('event name required');
	if (!(e.distance_m >= 800)) throw new Error('event distance must be at least 800 m');
	const today = todayLocal();
	if (e.event_date < today) throw new Error('event date must be today or later');
	const active = (await dbGet<{ n: number }>('SELECT COUNT(*) AS n FROM events WHERE event_date >= ?', [today]))?.n ?? 0;
	if (active > 0) throw new Error('one goal event at a time — delete or finish the current one first');
	const res = await dbRun(
		'INSERT INTO events (name, distance_m, event_date, target_time_min, category, created_at) VALUES (?, ?, ?, ?, ?, ?)',
		[e.name, e.distance_m, e.event_date, e.target_time_min, e.category?.trim() || null, Math.floor(Date.now() / 1000)]
	);
	const id = Number(res.lastInsertRowid);
	return { id, ...e, category: e.category?.trim() || null };
}

export async function deleteEvent(id: number): Promise<boolean> {
	const res = await dbRun('DELETE FROM events WHERE id = ?', [id]);
	return res.changes > 0;
}

/* ---------------- plan rows ---------------- */

export async function fetchSessions(fromDate: string, toDate: string): Promise<Session[]> {
	return dbAll<Session>(
		`SELECT plan_date, kind, label, distance_m, duration_min, pace_min_s_km,
		        pace_max_s_km, plan_week, reason
		 FROM planned_sessions WHERE plan_date >= ? AND plan_date <= ?
		 ORDER BY plan_date`,
		[fromDate, toDate]
	);
}

export async function replacePlanWindow(sessions: Session[]): Promise<void> {
	if (sessions.length === 0) return;
	const from = sessions.reduce((a, b) => (a.plan_date < b.plan_date ? a : b)).plan_date;
	// delete EVERYTHING from `from` onward — a shrunken horizon (race removed,
	// month rolled) must not leave stale rows that a future regen could re-read.
	await dbExec('BEGIN');
	try {
		await dbRun('DELETE FROM planned_sessions WHERE plan_date >= ?', [from]);
		const now = Math.floor(Date.now() / 1000);
		for (const s of sessions) {
			await dbRun(
				`INSERT INTO planned_sessions
				 (plan_date, kind, label, distance_m, duration_min, pace_min_s_km, pace_max_s_km, plan_week, reason, created_at)
				 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
				[s.plan_date, s.kind, s.label, s.distance_m, s.duration_min, s.pace_min_s_km, s.pace_max_s_km, s.plan_week, s.reason, now]
			);
		}
		await dbExec('COMMIT');
	} catch (err) {
		await dbExec('ROLLBACK');
		throw err;
	}
}

async function activitiesInWindow(fromDate: string, toDate: string): Promise<ActBrief[]> {
	return dbAll<ActBrief>(
		`SELECT strava_id, name, distance, start_date_local, trainer, commute, manual
		 FROM activities
		 WHERE substr(start_date_local, 1, 10) BETWEEN ? AND ?
		 ORDER BY start_date_local`,
		[fromDate, toDate]
	);
}

/** Plan view: existing sessions + events + matches. Generation is explicit
 *  (POST /api/plan/generate) so the UI can ask preferences first. */
export async function planView(limitDays: number | null, regenerate: boolean): Promise<{
	days: ReturnType<typeof matchPlan>;
	events: PlanEvent[];
	anchorKm: number;
	hasVdot: boolean;
	generated: boolean;
	prefs: PlanPrefs | null;
	coachNote: string[];
	horizon: { from: string; to: string; shownTo: string; isRace: boolean; name: string | null; daysTo: number };
}> {
	const today = todayLocal();
	const events = await listEvents();
	const horizon = planHorizon(today, events);
	// `limitDays` only narrows what is FETCHED/RENDERED (e.g. Home requests 7);
	// generation always spans the full horizon (month end or race date).
	const limitTo = limitDays ? addDays(today, Math.max(limitDays, 1) - 1) : null;
	const shownTo = limitTo && limitTo < horizon.to ? limitTo : horizon.to;
	const horizonDays = horizon.daysTo;

	const snapshot = await latestSnapshot();
	const vdotVal = snapshot?.vdot ?? null;

	const actsAll = await dbAll<ActRow>(
		`SELECT distance, start_date_local, trainer, commute, manual
		 FROM activities
		 WHERE substr(start_date_local, 1, 10) < ?
		 ORDER BY start_date_local DESC LIMIT 2000`,
		[today]
	);
	const anchorKm = volumeAnchorKm(actsAll, today);

	const prefs = await loadPrefs();
	let sessions = await fetchSessions(today, horizon.to);
	const shown = sessions.filter((s) => s.plan_date <= shownTo);
	const ctx = await buildAdjustCtx(today);
	let coachNote: string[] = [];
	const lastStored = sessions.length > 0 ? sessions[sessions.length - 1].plan_date : null;
	const covered = prefs !== null && lastStored !== null && lastStored >= horizon.to;
	if (regenerate || (!covered && prefs)) {
		sessions = await generatePlan({
			today,
			horizonDays,
			vdotVal,
			anchorKm,
			events,
			prefs: prefs ?? undefined
		});
		// S3: adjust today/tomorrow from journal + feedback + matcher
		const adj = await adjust(sessions, ctx);
		adj.sessions.forEach((s, i) => (sessions[i] = s));
		coachNote = adj.notes;
		await replacePlanWindow(sessions);
		return {
			days: matchPlan(sessions.filter((s) => s.plan_date <= shownTo), await activitiesInWindow(today, shownTo), today),
			events,
			anchorKm,
			hasVdot: vdotVal !== null,
			generated: true,
			prefs,
			coachNote,
			horizon: { from: today, to: horizon.to, shownTo, isRace: horizon.isRace, name: horizon.name, daysTo: horizon.daysTo }
		};
	}
	const adj = await adjust(shown, ctx); // advisory only, plan stays stored as built
	coachNote = adj.notes;
	const acts = await activitiesInWindow(today, shownTo);
	return {
		days: matchPlan(shown, acts, today),
		events,
		anchorKm,
		hasVdot: vdotVal !== null,
		generated: sessions.length > 0,
		prefs,
		coachNote,
		horizon: { from: today, to: horizon.to, shownTo, isRace: horizon.isRace, name: horizon.name, daysTo: horizon.daysTo }
	};
}

/* ---------------- activities + feedback (Activity tab) ---------------- */

export interface ActivityRow {
	strava_id: number;
	name: string;
	type: string | null;
	sport_type: string | null;
	start_date_local: string | null;
	distance: number;
	moving_time: number;
	average_speed: number;
	average_heartrate: number | null;
	max_heartrate: number | null;
	has_heartrate: number;
	trainer: number;
	commute: number;
	manual: number;
}

export async function recentActivities(limit = 60): Promise<ActivityRow[]> {
	return dbAll<ActivityRow>(
		`SELECT strava_id, name, type, sport_type, start_date_local, distance, moving_time,
		        average_speed, average_heartrate, max_heartrate, has_heartrate, trainer, commute, manual
		 FROM activities
		 ORDER BY substr(start_date_local, 1, 10) DESC, start_date_local DESC
		 LIMIT ?`,
		[limit]
	);
}

export interface Feedback {
	rpe: number | null;
	felt: string | null;
	soreness: string | null;
	note: string | null;
}

export async function feedbackFor(stravaIds: number[]): Promise<Map<number, Feedback>> {
	const map = new Map<number, Feedback>();
	if (stravaIds.length === 0) return map;
	const placeholders = stravaIds.map(() => '?').join(',');
	const rows = await dbAll<{ strava_id: number; rpe: number | null; felt: string | null; soreness: string | null; note: string | null }>(
		`SELECT strava_id, rpe, felt, soreness, note FROM feedback WHERE strava_id IN (${placeholders})`,
		stravaIds
	);
	for (const r of rows) {
		map.set(r.strava_id, { rpe: r.rpe, felt: r.felt, soreness: r.soreness, note: r.note });
	}
	return map;
}

export async function saveFeedback(f: {
	strava_id: number;
	rpe?: number | null;
	felt?: string | null;
	soreness?: string | null;
	note?: string | null;
}): Promise<void> {
	await dbRun(
		`INSERT INTO feedback (strava_id, rpe, felt, soreness, note, created_at)
		 VALUES (@strava_id, @rpe, @felt, @soreness, @note, @created_at)
		 ON CONFLICT(strava_id) DO UPDATE SET
		   rpe=@rpe, felt=@felt, soreness=@soreness, note=@note, created_at=@created_at`,
		{
			strava_id: f.strava_id,
			rpe: f.rpe ?? null,
			felt: f.felt ?? null,
			soreness: f.soreness ?? null,
			note: f.note ?? null,
			created_at: Math.floor(Date.now() / 1000)
		}
	);
}

/* ---------------- daily journal (S3) ---------------- */

export async function getJournal(date: string): Promise<(JournalState & { note: string | null }) | null> {
	const row = await dbGet<{ energy: number | null; sleep_h: number | null; soreness: string | null; note: string | null }>(
		'SELECT energy, sleep_h, soreness, note FROM journal WHERE date = ?',
		[date]
	);
	if (!row) return null;
	return { energy: row.energy, sleep_h: row.sleep_h, soreness: row.soreness as JournalState['soreness'], note: row.note };
}

export async function upsertJournal(
	date: string,
	j: { energy: number | null; sleep_h: number | null; soreness: string | null; note: string | null }
): Promise<void> {
	await dbRun(
		`INSERT INTO journal (date, energy, sleep_h, soreness, note, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?)
		 ON CONFLICT(date) DO UPDATE SET energy=excluded.energy, sleep_h=excluded.sleep_h, soreness=excluded.soreness, note=excluded.note, updated_at=excluded.updated_at`,
		[date, j.energy, j.sleep_h, j.soreness, j.note, Math.floor(Date.now() / 1000)]
	);
}

/** Context for the adjustment engine: today's journal, most recent rated
 *  workout (before today), and whether yesterday's planned session was missed. */
export async function buildAdjustCtx(today: string): Promise<AdjustCtx> {
	const journal = await getJournal(today);
	const lastRow = await dbGet<{
		rpe: number | null;
		felt: string | null;
		soreness: string | null;
		note: string | null;
		date: string;
	}>(
		`SELECT fb.strava_id, fb.rpe, fb.felt, fb.soreness, fb.note, a.start_date_local AS date
		 FROM feedback fb JOIN activities a ON a.strava_id = fb.strava_id
		 WHERE substr(a.start_date_local, 1, 10) < ?
		 ORDER BY a.start_date_local DESC LIMIT 1`,
		[today]
	);
	let last: AdjustCtx['last'] = null;
	if (lastRow) {
		const d = lastRow.date.slice(0, 10);
		const planned = await dbGet<{ kind: string }>(
			'SELECT kind FROM planned_sessions WHERE plan_date = ? AND kind != ? LIMIT 1',
			[d, 'rest']
		);
		last = { date: d, rpe: lastRow.rpe, felt: lastRow.felt, soreness: lastRow.soreness, note: lastRow.note, plannedKind: planned?.kind ?? null };
	}
	// missed yesterday? a planned run-session on yesterday with no qualifying run
	const y = addDays(today, -1);
	const yPlanned = await dbGet<{ kind: string }>(
		"SELECT kind FROM planned_sessions WHERE plan_date = ? AND kind != 'rest' AND kind != 'race' LIMIT 1",
		[y]
	);
	let missedYesterday = false;
	if (yPlanned) {
		const ran = await dbGet<{ n: number }>(
			`SELECT COUNT(*) AS n FROM activities
			 WHERE substr(start_date_local, 1, 10) = ? AND trainer = 0 AND commute = 0 AND manual = 0 AND distance > 0`,
			[y]
		);
		missedYesterday = ran?.n === 0;
	}
	return { journal, last, missedYesterday };
}

/** Swap one planned session's workout type in place (user picks speed/long/
 *  tempo/easy on a given day). Distance is kept; pace/label/reason refresh. */
export async function swapSessionKind(planDate: string, kind: Session['kind']): Promise<boolean> {
	const row = await dbGet<{ id: number; distance_m: number | null }>(
		'SELECT id, plan_date, kind, distance_m FROM planned_sessions WHERE plan_date = ? AND kind != ? AND kind != ? LIMIT 1',
		[planDate, 'rest', 'race']
	);
	if (!row || row.distance_m == null) return false;
	const meta: Record<string, { label: string; effort: string }> = {
		easy: { label: 'Easy run', effort: EFFORT.easy },
		quality: { label: 'Threshold', effort: EFFORT.quality },
		interval: { label: 'Speedwork', effort: EFFORT.interval },
		long: { label: 'Long run', effort: EFFORT.long }
	};
	const m = meta[kind];
	if (!m) return false;
	const label = `${m.label} · effort ${m.effort}/10`;
	await dbRun(
		'UPDATE planned_sessions SET kind = ?, label = ?, pace_min_s_km = NULL, pace_max_s_km = NULL, duration_min = NULL, reason = ? WHERE id = ?',
		[kind, label, `your pick — swapped to ${m.label}`, row.id]
	);
	return true;
}
