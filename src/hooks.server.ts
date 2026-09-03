import { startHourlySync } from '$lib/server/sync_scheduler';

/**
 * Single-user app: start the hourly Strava sync loop on first request.
 * `init` alone is unreliable under adapter-node, so we lazily start from
 * `handle` too (first request triggers it) — guaranteed to run.
 */
let started = false;
function ensureStarted(): void {
	if (started) return;
	started = true;
	startHourlySync();
}

export function init(): void {
	ensureStarted();
}

export async function handle({ event, resolve }) {
	ensureStarted();
	return resolve(event);
}
