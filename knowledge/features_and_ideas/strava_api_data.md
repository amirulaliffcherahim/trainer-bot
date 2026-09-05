# Strava v3 REST API — data catalog for a full personal copy

Source: developers.strava.com/docs/reference (single-page Swagger: all endpoint
groups + all models w/ field tables), plus authentication / rate-limits /
uploads / API-agreement pages. Crawled 2026-09. Research folder — NOT coach KB.

Structural note: the reference is ONE page containing every endpoint AND model —
no per-model pages. `resource_state` on objects: meta(1) / summary(2) / detail(3).
IDs are 64-bit — persist string forms (`upload_id_str`, `id_str`). Distances in
metres, speeds m/s, times seconds, elevation metres.

## Endpoint groups

- **Activities** — POST /activities (create manual, activity:write) → DetailedActivity;
  GET /activities/{id} → DetailedActivity (`include_all_efforts=true` returns all
  segment efforts); GET /athlete/activities → SummaryActivity[] (`before`/`after`
  epoch ts, `page`/`per_page` default 30); comments; kudos; laps; zones; update.
- **Athletes** — GET /athlete → DetailedAthlete; GET /athletes/{id}/stats →
  ActivityStats (only Everyone-visibility activities counted); zones; update.
- **Clubs** — GET /clubs/{id}; GET /athlete/clubs → SummaryClub[]. No club feed.
- **Gears** — GET /gear/{id} → DetailedGear (bike/shoe metadata + mileage).
- **Routes** — GET /routes/{id} → Route; GET /athletes/{id}/routes → Route[];
  export route as raw GPX or TCX file.
- **Segments** — explore; starred; GET /segments/{id} → DetailedSegment;
  star/unstar.
- **SegmentEfforts** — GET /segment_efforts?segment_id&start_date_local&end_date_local
  → DetailedSegmentEffort[] (**requires subscription**); GET /segment_efforts/{id}.
- **Streams** — GET /activities/{id}/streams?keys=...&key_by_type=true → StreamSet;
  route / segment / segment-effort stream variants. Requires activity:read
  (activity:read_all for Only-Me).
- **Uploads** — POST /uploads (multipart FIT/TCX/GPX/JSON, activity:write, async)
  then GET /uploads/{id} to poll.
- Running Races group no longer exists; no delete-activity endpoint.

## Data model — capture per activity

### Activity base (BOTH list SummaryActivity and detail)
- id, external_id, upload_id, upload_id_str
- name, type (deprecated), sport_type, workout_type
- start_date, start_date_local, timezone, utc_offset (in samples)
- distance, moving_time, elapsed_time, total_elevation_gain, elev_high, elev_low
- average_speed, max_speed
- flags: trainer, commute, manual, private, flagged, hide_from_home
- achievement_count, kudos_count, comment_count, athlete_count
- start_latlng, end_latlng (LatLng = [lat, lng])
- map → PolylineMap { id, summary_polyline } — full polyline is detail-only
- gear_id (string; full gear object detail-only)
- power fields when measured: kilojoules, average_watts, weighted_average_watts,
  max_watts, device_watts (rides w/ power meter)

### ONLY on DetailedActivity (GET /activities/{id})
- description, calories (kcal), device_name, embed_token
- gear → SummaryGear { id, primary, name, distance }
- map.polyline (full GPS trace), photos (PhotosSummary)
- laps: Lap[]; splits_metric + splits_standard: Split[] (per-km / per-mile run
  splits); best_efforts: DetailedSegmentEffort[] (PRs); segment_efforts:
  DetailedSegmentEffort[] (include_all_efforts=true for all)
- real payloads add fields absent from model tables — pr_count, average_cadence,
  average_temp, has_heartrate, max_watts, suffer_score, total_photo_count

### Lap (embedded or GET /activities/{id}/laps)
id, name, lap_index, split, distance, moving_time, elapsed_time,
total_elevation_gain, average_speed, max_speed, average_cadence, average_watts /
device_watts, pace_zone, start_date(+local), start_index / end_index (indices
into the activity stream).

### Splits (detail only)
Per split: distance, elapsed_time, moving_time, elevation_difference, split
index, average_speed, pace_zone.

### Efforts (segment_efforts + best_efforts — both DetailedSegmentEffort)
id, activity_id, name, distance, elapsed_time, moving_time, start_date(+local),
start_index, end_index, average_cadence, average_watts, device_watts, pr_rank,
kom_rank, is_kom, achievements[], hidden; segment → SummarySegment { id, name,
activity_type (Ride/Run), distance, average_grade, maximum_grade,
elevation_high/low, start/end_latlng, climb_category 0–5, city, state, country,
private, hazardous }. SummarySegment also has athlete_pr_effort (pr_activity_id,
pr_elapsed_time, pr_date, effort_count) and athlete_segment_stats.

### Streams (key_by_type=true → StreamSet)
Keys: time, distance, latlng, altitude, velocity_smooth, heartrate, cadence,
watts, temp, moving, grade_smooth. Each stream: original_size, resolution
(low/medium/high), series_type (distance|time = downsampling base), data[]
(typed: altitude m, cadence rpm, heartrate bpm, watts, temp C, moving boolean,
distance m, velocity_smooth m/s, latlng pairs).

### Athlete / stats / gear / route (enrichment)
- SummaryAthlete: id, firstname, lastname, profile_medium (62px), profile
  (124px), city, state, country, sex (M/F), premium(deprecated)/summit,
  created_at, updated_at. GET /athlete → DetailedAthlete.
- ActivityStats: biggest_ride_distance, biggest_climb_elevation_gain + recent
  (4 wk)/ytd/all-time ride·run·swim totals. ActivityTotal: count, distance,
  moving_time, elapsed_time, elevation_gain, achievement_count.
- DetailedGear: id, primary, name, distance, brand_name, model_name, frame_type,
  description.
- Route: athlete, name, description, distance, elevation_gain, type
  (1 Ride … 7 MTB Ride), sub_type, map, segments (SummarySegment[]), waypoints
  (latlng), created_at/updated_at, estimated_moving_time, starred, private.
  GPX/TCX export = full original route copy.

## Notes (limits, scopes, ownership)

- **Rate limits**: default overall 200 req/15 min, 2000/day; "non-upload"
  100/15 min, 1000/day (everything except POST /activities, POST /uploads,
  upload_media). 15-min window resets at natural quarter-hours; daily resets UTC
  midnight. Usage via X-RateLimit-Limit/Usage (+X-ReadRateLimit-*); overflow →
  429. New apps start at athlete capacity 1 ("Single Player Mode" — app for
  yourself, own data OK); 10-athlete tier 200/15min + 2000/day read,
  400/15min + 4000/day overall.
- **Scopes**: activity:read = Everyone+Followers activities, EXCLUDES
  privacy-zone data; activity:read_all adds Only-Me + privacy-zone streams/latlng;
  activity:write = uploads/manual creates/edits. profile:read_all for full
  profile; read_all for private routes/segments. Athletes can uncheck scopes at
  auth. Access tokens expire ~6 h — always persist the newest (rotating) refresh
  token + per-athlete granted scopes.
- **Ownership/storage**: API Agreement (effective 2026-06-01) permits an app to
  hold the authorizing user's Strava data — the "own copy of own data" trainer
  case fits Single Player Mode. One user's Strava data may be displayed only to
  that user — never other users' data, even if public. Delete data on
  termination/deauthorization (POST /oauth/deauthorize; /oauth/revoke available
  2026+, mandatory 2027). Honor privacy choices + privacy zones.
- **Capture plan**: page GET /athlete/activities (before/after) → upsert base
  rows → per id fetch detail (laps, splits, best_efforts, segment_efforts,
  polyline, calories, description, gear) + GET /activities/{id}/streams for
  chosen keys. Per-segment effort HISTORY is subscription-only; activity-detail
  efforts are not — no subscription needed for a full own-data copy.

## Source URLs

- https://developers.strava.com/docs/reference/
- https://developers.strava.com/docs/authentication/
- https://developers.strava.com/docs/rate-limits/
- https://developers.strava.com/docs/uploads/
- https://www.strava.com/legal/api
