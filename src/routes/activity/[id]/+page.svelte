<script lang="ts">
	import { parseLocalIso } from '$lib/timefmt';
	import 'leaflet/dist/leaflet.css';
	import { onMount } from 'svelte';

	let { data } = $props();

	const a = $derived(data.activity);
	const streams = $derived(data.streams as Record<string, number[] | [number, number][] | null> | null);
	const WDAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	const fmtTime = (s: number) =>
		`${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
	const day = (iso: string) => {
		const d = parseLocalIso(iso);
		return `${WDAY[d.getDay()]}, ${d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`;
	};
	const psec = (s: number | null) =>
		s === null ? '' : `${Math.floor(Math.round(s) / 60)}:${String(Math.round(s) % 60).padStart(2, '0')}`;

	const dist = $derived((streams?.distance as number[] | undefined) ?? []);
	const alt = $derived((streams?.altitude as number[] | undefined) ?? []);
	const vel = $derived((streams?.velocity_smooth as number[] | undefined) ?? []);
	const coords = $derived((streams?.latlng as [number, number][] | undefined) ?? []);

	const W = 320;
	const H = 90;
	const PAD = 6;

	/** Elevation profile + per-km-ish pace chart, straight to SVG paths. */
	const charts = $derived.by(() => {
		const out = { climb: 0, elevPath: '', elevArea: '', pacePath: '', elevLow: 0, elevHigh: 0 };
		const n = Math.min(dist.length, alt.length);
		if (n > 10 && alt.length > 0) {
			const step = Math.max(1, Math.floor(n / 160));
			const pts: [number, number][] = [];
			let climb = 0;
			for (let i = 0; i < n; i += step) {
				const d = dist[i] / 1000;
				const e = alt[i] ?? 0;
				if (i > 0 && e > (alt[i - step] ?? 0)) climb += e - (alt[i - step] ?? 0);
				pts.push([d, e]);
			}
			pts.push([dist[n - 1] / 1000, alt[n - 1] ?? 0]);
			out.climb = climb;
			out.elevLow = Math.min(...pts.map((p) => p[1]));
			out.elevHigh = Math.max(...pts.map((p) => p[1]));
			const ds = pts.map((p) => p[0]);
			const es = pts.map((p) => p[1]);
			const dMin = Math.min(...ds);
			const dMax = Math.max(...ds);
			const span = Math.max(Math.max(...es) - Math.min(...es), 1);
			out.elevPath = pts
				.map(([d, e], i) => {
					const x = PAD + ((d - dMin) / Math.max(dMax - dMin, 1)) * (W - 2 * PAD);
					const y = H - PAD - ((e - out.elevLow) / span) * (H - 2 * PAD);
					return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
				})
				.join('');
			out.elevArea = `${out.elevPath} L${W - PAD},${H - PAD} L${PAD},${H - PAD} Z`;
		}
		if (dist.length > 10 && vel.length > 0) {
			const step = Math.max(1, Math.floor(Math.min(dist.length, vel.length) / 140));
			const pts: [number, number][] = [];
			for (let i = 0; i < Math.min(dist.length, vel.length); i += step) {
				const v = vel[i];
				if (v && v > 0) pts.push([dist[i] / 1000, 1000 / v]);
			}
			if (pts.length > 2) {
				const ds = pts.map((p) => p[0]);
				const ps = pts.map((p) => p[1]);
				const dMin = Math.min(...ds);
				const dMax = Math.max(...ds);
				const pMin = Math.max(Math.min(...ps) - 15, 1);
				const pMax = Math.max(...ps) + 15;
				out.pacePath = pts
					.map(([d, pa], i) => {
						const x = PAD + ((d - dMin) / Math.max(dMax - dMin, 1)) * (W - 2 * PAD);
						const y = PAD + (1 - (pa - pMin) / Math.max(pMax - pMin, 1)) * (H - 2 * PAD);
						return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
					})
					.join('');
			}
		}
		return out;
	});

	/* ---------- map (leaflet, lazy) ---------- */
	let mapEl: HTMLDivElement | undefined = $state();
	onMount(async () => {
		if (coords.length < 2 || !mapEl) return;
		const L = await import('leaflet');
		const map = L.map(mapEl, { attributionControl: true });
		L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
			maxZoom: 18,
			attribution: '© OpenStreetMap contributors'
		}).addTo(map);
		L.polyline(coords as [number, number][], { color: '#4f46e5', weight: 4 }).addTo(map);
		const start = coords[0] as [number, number];
		const end = coords[coords.length - 1] as [number, number];
		L.circleMarker(start, { radius: 6, color: '#16a34a', fillColor: '#16a34a', fillOpacity: 1 }).addTo(map);
		L.circleMarker(end, { radius: 6, color: '#dc2626', fillColor: '#dc2626', fillOpacity: 1 }).addTo(map);
		map.fitBounds(L.latLngBounds(coords.map(([la, lo]) => [la, lo] as [number, number])), { padding: [24, 24] });
	});
</script>

<svelte:head><title>{a?.name ?? 'Activity'} — trainer·bot</title></svelte:head>

{#if data.missing}
	<div class="empty"><div class="big">Activity not found</div></div>
{:else}
	<div class="card">
		<a class="subtle" href="/activities" style="text-decoration:none">← Activity list</a>
		<h2 style="margin:6px 0 2px">{a.name}</h2>
		<p class="subtle">
			{day(a.start_date_local)} · {Math.round(a.distance / 100) / 10} km · {fmtTime(a.moving_time)} · {psec(a.pace_sec_km)}/km
			{#if a.average_heartrate} · ❤ {Math.round(a.average_heartrate)}{/if}
			{#if charts.climb > 0} · ⛰ {charts.climb.toFixed(0)} m gain{/if}
		</p>
	</div>

	{#if !streams}
		<div class="card"><p class="subtle">{data.streamError ? 'No GPS streams available for this one.' : 'Loading charts…'}</p></div>
	{:else}
		{#if charts.elevPath}
			<div class="card">
				<h2>Elevation <span class="subtle">{charts.elevLow.toFixed(0)}–{charts.elevHigh.toFixed(0)} m</span></h2>
				<svg viewBox="0 0 320 90" width="100%" role="img" aria-label="elevation profile" style="color:var(--ink)">
					<path d={charts.elevArea} fill="currentColor" opacity="0.14" />
					<path d={charts.elevPath} fill="none" stroke="currentColor" stroke-width="2" />
				</svg>
			</div>
		{/if}
		{#if charts.pacePath}
			<div class="card">
				<h2>Pace <span class="subtle">s/km</span></h2>
				<svg viewBox="0 0 320 90" width="100%" role="img" aria-label="pace chart" style="color:var(--strava)">
					<path d={charts.pacePath} fill="none" stroke="currentColor" stroke-width="2" />
				</svg>
			</div>
		{/if}
		<div class="card">
			<h2>Route</h2>
			{#if coords.length >= 2}
				<div bind:this={mapEl} style="height:280px;border-radius:var(--radius-sm);overflow:hidden"></div>
			{:else}
				<p class="subtle">No GPS track recorded for this activity.</p>
			{/if}
		</div>
	{/if}
{/if}
