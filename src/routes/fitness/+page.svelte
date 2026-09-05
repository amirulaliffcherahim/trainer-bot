<script lang="ts">
	import { fmt_pace, fmt_time } from '$lib/vdot';
	import { onMount } from 'svelte';
	let { data } = $props();

	const eq = $derived([
		{ key: 'marathon', label: 'Marathon' },
		{ key: 'half', label: 'Half Marathon' },
		{ key: '15k', label: '15K' },
		{ key: '10k', label: '10K' },
		{ key: '5k', label: '5K' },
		{ key: 'mile', label: 'Mile' }
	]);

	/* unit preference — km default, persisted like the theme toggle */
	let unit = $state<'km' | 'mi'>('km');
	const paceKm = (perMi: number) => fmt_pace(perMi / 1.609344);
	const pace = (perMi: number) => (unit === 'km' ? paceKm(perMi) : fmt_pace(perMi));
	function setUnit(u: 'km' | 'mi') {
		unit = u;
		try {
			localStorage.setItem('tb-units', u);
		} catch {
			/* ignore */
		}
	}
	onMount(() => {
		let stored: string | null = null;
		try {
			stored = localStorage.getItem('tb-units');
		} catch {
			/* ignore */
		}
		if (stored === 'km' || stored === 'mi') unit = stored;
	});
</script>

<svelte:head><title>Fitness — trainer·bot</title></svelte:head>

{#if !data.derived}
	<div class="card">
		<div class="empty">
			<div class="big">No VO₂ estimate yet</div>
			Connect Strava and sync — your best recent efforts become your anchor.
		</div>
		<a class="btn" href="/settings">Settings</a>
	</div>
{:else}
	<div class="hero">
		<div class="label">Estimated VO₂ max</div>
		<div class="score">{data.derived.vdot.toFixed(1)}</div>
		{#if data.snapshot}
			<div class="src">from {data.snapshot.source_name ?? 'best effort'}
				· {Math.round(data.snapshot.source_distance / 100) / 10} km
				· {fmt_time(data.snapshot.source_time_min)}
				· {new Date(data.snapshot.source_date + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</div>
		{/if}
	</div>

	<div class="card">
		<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
			<h2 style="margin:0">Training paces</h2>
			<div class="chips" style="margin:0">
				<button class="chip {unit === 'km' ? 'on' : ''}" onclick={() => setUnit('km')} aria-pressed={unit === 'km'}>km</button>
				<button class="chip {unit === 'mi' ? 'on' : ''}" onclick={() => setUnit('mi')} aria-pressed={unit === 'mi'}>mi</button>
			</div>
		</div>
		<table class="tbl">
			<thead>
				<tr><th>Type</th><th class="num">{unit === 'km' ? 'min/km' : 'min/mi'}</th></tr>
			</thead>
			<tbody>
				<tr>
					<td>Easy</td>
					<td class="num">{pace(data.derived.paces.easy.slow)}–{pace(data.derived.paces.easy.fast)}</td>
				</tr>
				<tr><td>Marathon</td><td class="num">{pace(data.derived.paces.marathon)}</td></tr>
				<tr><td>Threshold</td><td class="num">{pace(data.derived.paces.threshold)}</td></tr>
				<tr><td>Interval</td><td class="num">{pace(data.derived.paces.interval)}</td></tr>
				<tr><td>Repetition</td><td class="num">{pace(data.derived.paces.repetition)}</td></tr>
				<tr><td>Fast reps</td><td class="num">{pace(data.derived.paces.fast_reps)}</td></tr>
			</tbody>
		</table>
	</div>

	<div class="card">
		<h2>Equivalent races</h2>
		<table class="tbl">
			<thead><tr><th>Race</th><th class="num">Time</th></tr></thead>
			<tbody>
				{#each eq as e (e.key)}
					<tr>
						<td>{e.label}</td>
						<td class="num">{fmt_time(data.derived.equivalents[e.key])}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
