import { getDb } from './db';

export interface StoredToken {
	access_token: string;
	refresh_token: string;
	expires_at: number; // epoch seconds
	scope: string;
	athlete_id: number | null;
	athlete_name: string | null;
}

export function getToken(): StoredToken | null {
	const row = getDb()
		.prepare('SELECT * FROM strava_token WHERE id = 1')
		.get() as StoredToken | undefined;
	return row ?? null;
}

/** Persist tokens. Strava rotates refresh tokens — ALWAYS store the one just
 *  returned; the previous refresh token dies immediately. */
export function putToken(t: StoredToken): void {
	getDb()
		.prepare(
			`INSERT INTO strava_token
			 (id, access_token, refresh_token, expires_at, scope, athlete_id, athlete_name, updated_at)
			 VALUES (1, @access_token, @refresh_token, @expires_at, @scope, @athlete_id, @athlete_name, @updated_at)
			 ON CONFLICT(id) DO UPDATE SET
			   access_token=@access_token, refresh_token=@refresh_token,
			   expires_at=@expires_at, scope=@scope, athlete_id=@athlete_id,
			   athlete_name=@athlete_name, updated_at=@updated_at`
		)
		.run({ ...t, updated_at: Math.floor(Date.now() / 1000) });
}

export function clearToken(): void {
	getDb().prepare('DELETE FROM strava_token WHERE id = 1').run();
}

/** True when an access token is valid for at least `minLeewaySec` more. */
export function tokenUsable(leewaySec = 3600): boolean {
	const t = getToken();
	if (!t) return false;
	return t.expires_at - Math.floor(Date.now() / 1000) > leewaySec;
}
