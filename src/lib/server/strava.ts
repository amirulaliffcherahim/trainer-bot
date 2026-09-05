import { env } from '$env/dynamic/private';
import { clearToken, getToken, putToken } from './token_store';

/**
 * Strava API v3 client — see knowledge/strava_api/strava_api_research.md.
 * Base: https://www.strava.com/api/v3/
 */

const API_BASE = 'https://www.strava.com/api/v3';
const OAUTH_TOKEN = 'https://www.strava.com/oauth/token';

export function stravaConfig(): { clientId: string; clientSecret: string; publicBaseUrl: string } | null {
	const clientId = env.STRAVA_CLIENT_ID;
	const clientSecret = env.STRAVA_CLIENT_SECRET;
	if (!clientId || !clientSecret) return null;
	return {
		clientId,
		clientSecret,
		publicBaseUrl: env.APP_BASE_URL || 'http://localhost:5173'
	};
}

export function authorizeUrl(): string {
	const cfg = stravaConfig();
	if (!cfg) throw new Error('Strava not configured');
	const q = new URLSearchParams({
		client_id: cfg.clientId,
		redirect_uri: `${cfg.publicBaseUrl}/api/auth/callback`,
		response_type: 'code',
		scope: 'activity:read,activity:read_all',
		approval_prompt: 'auto'
	});
	return `https://www.strava.com/oauth/authorize?${q}`;
}

export class StravaError extends Error {
	constructor(
		message: string,
		public status: number,
		public retryAfterSec: number | null = null,
		public rateUsage: string | null = null
	) {
		super(message);
	}
}

/** Exchange an authorization code (or refresh) for a token pair. */
async function exchange(params: Record<string, string>): Promise<void> {
	const cfg = stravaConfig();
	if (!cfg) throw new Error('Strava not configured');
	const body = new URLSearchParams({
		client_id: cfg.clientId,
		client_secret: cfg.clientSecret,
		...params
	});
	const res = await fetch(OAUTH_TOKEN, { method: 'POST', body });
	if (!res.ok) {
		const text = await res.text();
		throw new StravaError(`Token exchange failed (${res.status}): ${text.slice(0, 200)}`, res.status);
	}
	const data = (await res.json()) as {
		access_token: string;
		refresh_token: string;
		expires_at: number;
		scope?: string;
		athlete?: { id: number; firstname?: string; lastname?: string };
	};
	await putToken({
		access_token: data.access_token,
		refresh_token: data.refresh_token, // rotation: persist THIS one
		expires_at: data.expires_at,
		scope: data.scope ?? '',
		athlete_id: data.athlete?.id ?? null,
		athlete_name: data.athlete ? `${data.athlete.firstname ?? ''} ${data.athlete.lastname ?? ''}`.trim() : null
	});
}

export async function exchangeCode(code: string): Promise<void> {
	const cfg = stravaConfig();
	if (!cfg) throw new Error('Strava not configured');
	await exchange({
		grant_type: 'authorization_code',
		code,
		client_id: cfg.clientId,
		client_secret: cfg.clientSecret
	});
}

async function refresh(): Promise<void> {
	const cfg = stravaConfig();
	const t = await getToken();
	if (!cfg || !t) throw new StravaError('No token to refresh', 401);
	await exchange({
		grant_type: 'refresh_token',
		refresh_token: t.refresh_token,
		client_id: cfg.clientId,
		client_secret: cfg.clientSecret
	});
}

async function accessToken(): Promise<string> {
	const t = await getToken();
	if (!t) throw new StravaError('Not connected to Strava', 401);
	// Refresh when expired or expiring within the hour (Strava's guidance).
	const nowSec = Math.floor(Date.now() / 1000);
	if (t.expires_at - nowSec <= 3600) {
		await refresh();
		return (await getToken())!.access_token;
	}
	return t.access_token;
}

interface ApiResponse<T> {
	data: T;
	rateUsage: { limit15: string; daily: string };
}

/** GET /api/v3/<path> with automatic token refresh on expiry. */
export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
	let token = await accessToken();
	const doGet = async (tok: string) =>
		fetch(`${API_BASE}${path}`, {
			headers: { Authorization: `Bearer ${tok}` }
		});
	const usageOf = (res: Response) => ({
		limit15: res.headers.get('x-ratelimit-limit') ?? '',
		daily: res.headers.get('x-ratelimit-usage') ?? ''
	});

	let res = await doGet(token);
	const usage = usageOf(res);
	if (res.status === 401) {
		// Token may have been revoked server-side. Refresh ONCE and retry;
		// never destroy stored tokens — a permanent 401 usually means
		// insufficient scope, which only a fresh consent can fix.
		await refresh();
		token = (await getToken())!.access_token;
		res = await doGet(token);
	}
	if (res.status === 401) {
		const scope = (await getToken())?.scope ?? '';
		throw new StravaError(
			`Strava authorization problem (401). Granted scopes: ${scope || 'none'} — ` +
				'connect again in Settings to request activity:read.',
			401
		);
	}
	if (res.status === 429) {
		throw new StravaError('Strava rate limit hit', 429, null, JSON.stringify(usage));
	}
	if (!res.ok) {
		const text = await res.text();
		throw new StravaError(`Strava API ${res.status}: ${text.slice(0, 200)}`, res.status);
	}
	return { data: (await res.json()) as T, rateUsage: usage };
}

/** Remove the app's access (deauthorize on Strava side too, best-effort). */
export async function disconnect(): Promise<void> {
	const t = await getToken();
	if (t) {
		try {
			const cfg = stravaConfig();
			if (cfg) {
				const body = new URLSearchParams({ access_token: t.access_token });
				await fetch('https://www.strava.com/oauth/deauthorize', { method: 'POST', body });
			}
		} catch {
			// best-effort — local disconnect still happens
		}
	}
	await clearToken();
}
