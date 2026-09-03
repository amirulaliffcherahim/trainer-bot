/**
 * Strava date helpers. `start_date_local` arrives as the athlete's LOCAL
 * clock time formatted with a `Z` suffix (no real offset) — parsing it as
 * UTC and rendering device-local shifts evening runs to the next day.
 * Treat it as naive local time: strip the zone suffix, parse as-is.
 */

/** '2026-09-03T21:30:00Z' | '...T21:30:00+08:00' -> Date in local wall time. */
export function parseLocalIso(iso: string): Date {
	// naive local wall clock: drop 'Z' or any +hh:mm suffix
	const naive = iso.replace(/Z$/, '').replace(/([+-]\d{2}):?\d{2}$/, '');
	return new Date(naive);
}
