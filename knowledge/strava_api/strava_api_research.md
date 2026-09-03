# Strava API — Research Notes (for trainer-bot data layer)

> Distilled from official docs (developers.strava.com — reference,
> authentication, rate-limits, webhooks pages; fetched 2026-09). Purpose:
> architect trainer-bot's athlete-data pipeline. Base URL:
> `https://www.strava.com/api/v3/`.

## Auth — OAuth2, three-legged
- Register app at strava.com/settings/api → client_id + client_secret (never
  ship/leak the secret).
- **Authorize (web):** `GET https://www.strava.com/oauth/authorize` with
  `client_id`, `redirect_uri` (must match app's callback domain;
  localhost/127.0.0.1 whitelisted), `response_type=code`,
  `approval_prompt=auto|force`, `scope`, `state`.
- Strava redirects back: accepted → `?code&scope`; denied → `?error=access_denied`.
  Granted scope can be SMALLER than requested (user unchecks boxes) — store
  what came back, verify before assuming.
- **Token exchange:** `POST https://www.strava.com/oauth/token`
  (`client_id`, `client_secret`, `code`, `grant_type=authorization_code`) →
  `{access_token, refresh_token, expires_at, expires_in, athlete, scope}`.
- **Access token lifetime: 6 hours** (`expires_in: 21600`).
- **Refresh:** same endpoint with `grant_type=refresh_token` + current
  `refresh_token`. **Refresh tokens rotate** — response returns a new one;
  persist the returned value, older one is invalidated immediately. If access
  token still has > 1 h left, the existing one is returned; else a new pair.
- Every API call: header `Authorization: Bearer <access_token>`.
- Deauth: `POST /oauth/deauthorize`; recommended now: `POST /oauth/revoke`
  (HTTP Basic with client_id:secret) — becomes the only endpoint June 2027.

## Scopes (ask for the minimum)
- `read` / `read_all` — profile/routes/segments public vs private.
- `profile:read_all` — full profile despite visibility settings.
- `profile:write` — update weight + FTP, star/unstar segments.
- `activity:read` — activities visible Everyone/Followers, no privacy zones.
- `activity:read_all` — adds Only You activities + privacy-zone data.
- `activity:write` — create manual activities, uploads, edit activities.
- `activity:read` is required for activity webhooks.

## Endpoint map (v3) that matters
- **Activities:** `POST /activities` (manual entry); `GET /activities/{id}`
  (+`include_all_efforts`); `GET /athlete/activities` — list, filters
  `before`/`after` (epoch), `page`, `per_page` (default 30); comments, kudos,
  laps sub-endpoints; `GET /activities/{id}/zones`; `PUT /activities/{id}`
  (edit). Requires `activity:read(_all)`.
- **Athletes:** `GET /athlete` (profile); `GET /athlete/zones`;
  `GET /athletes/{id}/stats`; `PUT /athlete`.
- **Stats payload:** `recent_*`/`ytd_*`/`all_*_totals` per sport (count,
  distance, moving_time, elapsed_time) + biggest ride/climb — **cheap volume
  summary without listing activities**. ⚠ only activities visible to
  Everyone are counted.
- **Uploads:** `POST /uploads` (multipart FIT/GPX/TCX, `activity:write`) →
  processing id; poll `GET /uploads/{id}` for status.
- **Streams:** `GET /activities/{id}/streams?keys=…&key_by_type` — per-second
  arrays: `time, distance, latlng, altitude, velocity_smooth, heartrate,
  cadence, watts, temp, moving, grade_smooth`. Route/segment-effort/segment
  stream variants exist.
- **Routes/segments/efforts:** routes list + GPX/TCX export; segments
  explore/star; segment efforts per segment/activity.

## Rate limits & app tiers (architecture-critical)
- Defaults: **overall 200 req / 15 min and 2 000 / day**; **non-upload
  100 / 15 min and 1 000 / day** (uploads = create activity, create upload,
  upload media — excluded from the non-upload bucket).
- Headers on every response: `X-RateLimit-Limit` & `X-RateLimit-Usage`
  (values "15min,daily"); `X-ReadRateLimit-*` mirrors the non-upload bucket.
  429 Too Many Requests when exceeded. 15-min window resets at :00/:15/:30/
  :45; daily resets midnight UTC.
- **Athlete capacity: new apps start at 1 athlete — "Single Player Mode".**
  Perfect for a personal tool. Upgrading from the API settings dashboard →
  capacity 10, read 200/15min & 2 000/day, overall 400 & 4 000/day.
  Beyond 10 athletes requires Strava app review.
- Strava's own advice: if polling burns limits → use webhooks.

## Webhooks (push events — no polling)
- One subscription per app; events for athletes that authorized you.
- Events: activity `create` / `update` / `delete`; athlete deauthorization.
  Activity update keys: `title`, `type`, `private`. Only-You visibility
  updates only with `activity:read_all` (with `activity:read` only, visibility
  flips read/private arrive as delete/create).
- Payload: `object_type` (activity|athlete), `object_id`, `aspect_type`,
  `updates{}`, `owner_id`, `subscription_id`, `event_time`. Deauth →
  `updates.authorized = false`.
- Callback must answer **HTTP 200 within 2 seconds**; else Strava retries up
  to 3 attempts. Heavy processing must be async.
- Lifecycle: `POST /push_subscriptions` (client_id, client_secret,
  callback_url ≤ 255 chars, verify_token) → Strava GETs your callback with
  `hub.mode=subscribe&hub.challenge=…&hub.verify_token=…` → echo
  `hub.challenge` as JSON within 2 s → you get subscription id. Manage via
  `GET /push_subscriptions`, `DELETE /push_subscriptions/{id}`.

## Activity fields that feed training math (DetailedActivity)
- distance (m), moving_time & elapsed_time (s), average_speed (m/s),
  max_speed, average_cadence, `has_heartrate` + average/max heartrate,
  total_elevation_gain, elev_high/low, calories, trainer/commute/manual/
  private/flagged flags, workout_type, gear, device_name (attribution),
  `splits_metric` (≈ per-km splits incl. pace_zone), `laps`, `segment_efforts`
  (PR/KOM ranks), start_date(_local), timezone, map polyline.

## Gaps & gotchas for our app
- **No cross-activity "best efforts" endpoint** — VDOT anchors must be
  computed client-side: scan `GET /athlete/activities` and use
  distance+moving_time (best recent effort per target distance), or read
  per-activity detail for splits. Never assume an activity has HR
  (`has_heartrate`).
- No public race-calendar/events API → goal events stay manual input.
- Privacy: Only You activities need `activity:read_all`; stats endpoint only
  sees Everyone-visibility; respect privacy zones (webhooks + read_all rules).
- Attribution/brand rules apply (show "Connect with Strava", credit data
  source device) — Strava guidelines before launch.

## Sources
- developers.strava.com/docs/reference/ (endpoints + DetailedActivity sample)
- developers.strava.com/docs/authentication/ (OAuth2, scopes, token refresh)
- developers.strava.com/docs/rate-limits/ (tiers, buckets, headers)
- developers.strava.com/docs/webhooks/ (subscriptions, events, validation)
