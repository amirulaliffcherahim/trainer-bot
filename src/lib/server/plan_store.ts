import { getDb } from './db';
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

export function loadPrefs(): PlanPrefs | null {
	const row = getDb().prepare('SELECT run_days, hard_days, kinds FROM plan_prefs WHERE id = 1').get() as
		| { run_days: string; hard_days: string; kinds: string | null }
		| undefined;
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

export function savePrefs(p: PlanPrefs): void {
	const valid = p.runDays.filter((d) => Number.isInteger(d) && d >= 0 && d <= 6);
	const kinds = p.kinds && Object.keys(p.kinds).length > 0 ? p.kinds : null;
	const hard = kinds
		? valid.filter((d) => kinds[d] === 'quality' || kinds[d] === 'interval')
		: [...new Set(p.hardDays.filter((d) => valid.includes(d)))].sort((a, b) => a - b);
	if (valid.length < 2) throw new Error('pick at least 2 training days');
	const db = getDb();
	db.prepare(
		`INSERT INTO plan_prefs (id, run_days, hard_days, kinds, updated_at)
		 VALUES (1, ?, ?, ?, ?)
		 ON CONFLICT(id) DO UPDATE SET run_days=excluded.run_days, hard_days=excluded.hard_days, kinds=excluded.kinds, updated_at=excluded.updated_at`
	).run(
		JSON.stringify(valid.sort((a, b) => a - b)),
		JSON.stringify(hard),
		kinds ? JSON.stringify(kinds) : null,
		Math.floor(Date.now() / 1000)
	);
}

/* ---------------- events ---------------- */

export function listEvents(): PlanEvent[] {
	return getDb()
		.prepare('SELECT id, name, distance_m, event_date, target_time_min, category FROM events ORDER BY event_date')
		.all() as unknown as PlanEvent[];
}

export function addEvent(e: {
	name: string;
	distance_m: number;
	event_date: string;
	target_time_min: number | null;
	category?: string | null;
}): PlanEvent {
	const db = getDb();
	if (!e.name.trim()) throw new Error('event name required');
	if (!(e.distance_m >= 800)) throw new Error('event distance must be at least 800 m');
	const today = todayLocal();
	if (e.event_date < today) throw new Error('event date must be today or later');
	const active = db.prepare('SELECT COUNT(*) AS n FROM events WHERE event_date >= ?').get(today) as { n: number };
	if (active.n > 0) throw new Error('one goal event at a time — delete or finish the current one first');
	const res = db
		.prepare('INSERT INTO events (name, distance_m, event_date, target_time_min, category, created_at) VALUES (?, ?, ?, ?, ?, ?)')
		.run(e.name, e.distance_m, e.event_date, e.target_time_min, e.category?.trim() || null, Math.floor(Date.now() / 1000));
	const id = Number(res.lastInsertRowid);
	return { id, ...e, category: e.category?.trim() || null };
}

export function deleteEvent(id: number): boolean {
	const res = getDb().prepare('DELETE FROM events WHERE id = ?').run(id);
	return res.changes > 0;
}

/* ---------------- plan rows ---------------- */

export function fetchSessions(fromDate: string, toDate: string): Session[] {
	return getDb()
		.prepare(
			`SELECT plan_date, kind, label, distance_m, duration_min, pace_min_s_km,
			        pace_max_s_km, plan_week, reason
			 FROM planned_sessions WHERE plan_date >= ? AND plan_date <= ?
			 ORDER BY plan_date`
		)
		.all(fromDate, toDate) as unknown as Session[];
}

export function replacePlanWindow(sessions: Session[]): void {
	const db = getDb();
	if (sessions.length === 0) return;
	const from = sessions.reduce((a, b) => (a.plan_date < b.plan_date ? a : b)).plan_date;
	// delete EVERYTHING from `from` onward — a shrunken horizon (race removed,
	// month rolled) must not leave stale rows that a future regen could re-read.
	db.exec('BEGIN');
	try {
		db.prepare('DELETE FROM planned_sessions WHERE plan_date >= ?').run(from);
		const ins = db.prepare(
			`INSERT INTO planned_sessions
			 (plan_date, kind, label, distance_m, duration_min, pace_min_s_km, pace_max_s_km, plan_week, reason, created_at)
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
		);
		const now = Math.floor(Date.now() / 1000);
		for (const s of sessions) {
			ins.run(s.plan_date, s.kind, s.label, s.distance_m, s.duration_min, s.pace_min_s_km, s.pace_max_s_km, s.plan_week, s.reason, now);
		}
		db.exec('COMMIT');
	} catch (err) {
		db.exec('ROLLBACK');
		throw err;
	}
}

function activitiesInWindow(fromDate: string, toDate: string): ActBrief[] {
	return getDb()
		.prepare(
			`SELECT strava_id, name, distance, start_date_local, trainer, commute, manual
			 FROM activities
			 WHERE substr(start_date_local, 1, 10) BETWEEN ? AND ?
			 ORDER BY start_date_local`
		)
		.all(fromDate, toDate) as unknown as ActBrief[];
}

/** Plan view: existing sessions + events + matches. Generation is explicit
 *  (POST /api/plan/generate) so the UI can ask preferences first. */
export function planView(limitDays: number | null, regenerate: boolean): {
	days: ReturnType<typeof matchPlan>;
	events: PlanEvent[];
	anchorKm: number;
	hasVdot: boolean;
	generated: boolean;
	prefs: PlanPrefs | null;
	coachNote: string[];
	horizon: { from: string; to: string; shownTo: string; isRace: boolean; name: string | null; daysTo: number };
} {
	const today = todayLocal();
	const events = listEvents();
	const horizon = planHorizon(today, events);
	// `limitDays` only narrows what is FETCHED/RENDERED (e.g. Home requests 7);
	// generation always spans the full horizon (month end or race date).
	const limitTo = limitDays ? addDays(today, Math.max(limitDays, 1) - 1) : null;
	const shownTo = limitTo && limitTo < horizon.to ? limitTo : horizon.to;
	const horizonDays = horizon.daysTo;

	const snapshot = latestSnapshot();
	const vdotVal = snapshot?.vdot ?? null;

	const actsAll = getDb()
		.prepare(
			`SELECT distance, start_date_local, trainer, commute, manual
			 FROM activities
			 WHERE substr(start_date_local, 1, 10) < ?
			 ORDER BY start_date_local DESC LIMIT 2000`
		)
		.all(today) as unknown as ActRow[];
	const anchorKm = volumeAnchorKm(actsAll, today);

	const prefs = loadPrefs();
	let sessions = fetchSessions(today, horizon.to);
	const shown = sessions.filter((s) => s.plan_date <= shownTo);
	const ctx = buildAdjustCtx(today);
	let coachNote: string[] = [];
	const lastStored = sessions.length > 0 ? sessions[sessions.length - 1].plan_date : null;
	const covered = prefs !== null && lastStored !== null && lastStored >= horizon.to;
	if (regenerate || (!covered && prefs)) {
		sessions = generatePlan({
			today,
			horizonDays,
			vdotVal,
			anchorKm,
			events,
			prefs: prefs ?? undefined
		});
		// S3: adjust today/tomorrow from journal + feedback + matcher
		const adj = adjust(sessions, ctx);
		adj.sessions.forEach((s, i) => (sessions[i] = s));
		coachNote = adj.notes;
		replacePlanWindow(sessions);
		return {
			days: matchPlan(sessions.filter((s) => s.plan_date <= shownTo), activitiesInWindow(today, shownTo), today),
			events,
			anchorKm,
			hasVdot: vdotVal !== null,
			generated: true,
			prefs,
			coachNote,
			horizon: { from: today, to: horizon.to, shownTo, isRace: horizon.isRace, name: horizon.name, daysTo: horizon.daysTo }
		};
	}
	const adj = adjust(shown, ctx); // advisory only, plan stays stored as built
	coachNote = adj.notes;
	const acts = activitiesInWindow(today, shownTo);
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

export function recentActivities(limit = 60): ActivityRow[] {
	return getDb()
		.prepare(
			`SELECT strava_id, name, type, sport_type, start_date_local, distance, moving_time,
			        average_speed, average_heartrate, max_heartrate, has_heartrate, trainer, commute, manual
			 FROM activities
			 ORDER BY substr(start_date_local, 1, 10) DESC, start_date_local DESC
			 LIMIT ?`
		)
		.all(limit) as unknown as ActivityRow[];
}

export interface Feedback {
	rpe: number | null;
	felt: string | null;
	soreness: string | null;
	note: string | null;
}

export function feedbackFor(stravaIds: number[]): Map<number, Feedback> {
	const map = new Map<number, Feedback>();
	if (stravaIds.length === 0) return map;
	const placeholders = stravaIds.map(() => '?').join(',');
	const rows = getDb()
		.prepare(`SELECT strava_id, rpe, felt, soreness, note FROM feedback WHERE strava_id IN (${placeholders})`)
		.all(...stravaIds) as unknown as { strava_id: number; rpe: number | null; felt: string | null; soreness: string | null; note: string | null }[];
	for (const r of rows) {
		map.set(r.strava_id, { rpe: r.rpe, felt: r.felt, soreness: r.soreness, note: r.note });
	}
	return map;
}

export function saveFeedback(f: { strava_id: number; rpe?: number | null; felt?: string | null; soreness?: string | null; note?: string | null }): void {
	getDb()
		.prepare(
			`INSERT INTO feedback (strava_id, rpe, felt, soreness, note, created_at)
			 VALUES (@strava_id, @rpe, @felt, @soreness, @note, @created_at)
			 ON CONFLICT(strava_id) DO UPDATE SET
			   rpe=@rpe, felt=@felt, soreness=@soreness, note=@note, created_at=@created_at`
		)
		.run({
			strava_id: f.strava_id,
			rpe: f.rpe ?? null,
			felt: f.felt ?? null,
			soreness: f.soreness ?? null,
			note: f.note ?? null,
			created_at: Math.floor(Date.now() / 1000)
		});
}

/* ---------------- daily journal (S3) ---------------- */

export function getJournal(date: string): (JournalState & { note: string | null }) | null {
	const row = getDb().prepare('SELECT energy, sleep_h, soreness, note FROM journal WHERE date = ?').get(date) as
		| { energy: number | null; sleep_h: number | null; soreness: string | null; note: string | null }
		| undefined;
	if (!row) return null;
	return { energy: row.energy, sleep_h: row.sleep_h, soreness: row.soreness as JournalState['soreness'], note: row.note };
}

export function upsertJournal(date: string, j: { energy: number | null; sleep_h: number | null; soreness: string | null; note: string | null }): void {
	getDb()
		.prepare(
			`INSERT INTO journal (date, energy, sleep_h, soreness, note, updated_at)
			 VALUES (?, ?, ?, ?, ?, ?)
			 ON CONFLICT(date) DO UPDATE SET energy=excluded.energy, sleep_h=excluded.sleep_h, soreness=excluded.soreness, note=excluded.note, updated_at=excluded.updated_at`
		)
		.run(date, j.energy, j.sleep_h, j.soreness, j.note, Math.floor(Date.now() / 1000));
}

/** Context for the adjustment engine: today's journal, most recent rated
 *  workout (before today), and whether yesterday's planned session was missed. */
export function buildAdjustCtx(today: string): AdjustCtx {
	const journal = getJournal(today);
	const lastRow = getDb()
		.prepare(
			`SELECT fb.strava_id, fb.rpe, fb.felt, fb.soreness, fb.note, a.start_date_local AS date
			 FROM feedback fb JOIN activities a ON a.strava_id = fb.strava_id
			 WHERE substr(a.start_date_local, 1, 10) < ?
			 ORDER BY a.start_date_local DESC LIMIT 1`
		)
		.get(today) as { rpe: number | null; felt: string | null; soreness: string | null; note: string | null; date: string } | undefined;
	let last = null;
	if (lastRow) {
		const d = lastRow.date.slice(0, 10);
		const planned = getDb()
			.prepare('SELECT kind FROM planned_sessions WHERE plan_date = ? AND kind != ? LIMIT 1')
			.get(d, 'rest') as { kind: string } | undefined;
		last = { date: d, rpe: lastRow.rpe, felt: lastRow.felt, soreness: lastRow.soreness, note: lastRow.note, plannedKind: planned?.kind ?? null };
	}
	// missed yesterday? a planned run-session on yesterday with no qualifying run
	const y = addDays(today, -1);
	const yPlanned = getDb()
		.prepare("SELECT kind FROM planned_sessions WHERE plan_date = ? AND kind != 'rest' AND kind != 'race' LIMIT 1")
		.get(y) as { kind: string } | undefined;
	let missedYesterday = false;
	if (yPlanned) {
		const ran = getDb()
			.prepare(
				`SELECT COUNT(*) AS n FROM activities
				 WHERE substr(start_date_local, 1, 10) = ? AND trainer = 0 AND commute = 0 AND manual = 0 AND distance > 0`
			)
			.get(y) as { n: number };
		missedYesterday = ran.n === 0;
	}
	return { journal, last: last as AdjustCtx['last'], missedYesterday };
}

/** Swap one planned session's workout type in place (user picks speed/long/
 *  tempo/easy on a given day). Distance is kept; pace/label/reason refresh. */
export function swapSessionKind(planDate: string, kind: Session['kind']): boolean {
	const row = getDb().prepare('SELECT id, plan_date, kind, distance_m FROM planned_sessions WHERE plan_date = ? AND kind != ? AND kind != ? LIMIT 1').get(planDate, 'rest', 'race') as
		| { id: number; distance_m: number | null }
		| undefined;
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
	getDb()
		.prepare('UPDATE planned_sessions SET kind = ?, label = ?, pace_min_s_km = NULL, pace_max_s_km = NULL, duration_min = NULL, reason = ? WHERE id = ?')
		.run(kind, label, `your pick — swapped to ${m.label}`, row.id);
	return true;
}
