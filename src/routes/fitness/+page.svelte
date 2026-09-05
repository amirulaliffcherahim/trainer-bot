<script lang="ts">
	import { fmt_pace, fmt_time } from '$lib/vdot';
	let { data } = $props();

	const eq = $derived([
		{ key: 'marathon', label: 'Marathon' },
		{ key: 'half', label: 'Half Marathon' },
		{ key: '15k', label: '15K' },
		{ key: '10k', label: '10K' },
		{ key: '5k', label: '5K' },
		{ key: 'mile', label: 'Mile' }
	]);
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
		<h2>Training paces</h2>
		<table class="tbl">
			<thead>
				<tr><th>Type</th><th class="num">min/mi</th><th class="num">min/km</th></tr>
			</thead>
			<tbody>
				<tr>
					<td>Easy</td>
					<td class="num">{fmt_pace(data.derived.paces.easy.slow)}–{fmt_pace(data.derived.paces.easy.fast)}</td>
					<td class="num">{fmt_pace(data.derived.paces.easy.slow / 1.609344)}–{fmt_pace(data.derived.paces.easy.fast / 1.609344)}</td>
				</tr>
				<tr><td>Marathon</td><td class="num">{fmt_pace(data.derived.paces.marathon)}</td><td class="num">{fmt_pace(data.derived.paces.marathon / 1.609344)}</td></tr>
				<tr><td>Threshold</td><td class="num">{fmt_pace(data.derived.paces.threshold)}</td><td class="num">{fmt_pace(data.derived.paces.threshold / 1.609344)}</td></tr>
				<tr><td>Interval</td><td class="num">{fmt_pace(data.derived.paces.interval)}</td><td class="num">{fmt_pace(data.derived.paces.interval / 1.609344)}</td></tr>
				<tr><td>Repetition</td><td class="num">{fmt_pace(data.derived.paces.repetition)}</td><td class="num">{fmt_pace(data.derived.paces.repetition / 1.609344)}</td></tr>
				<tr><td>Fast reps</td><td class="num">{fmt_pace(data.derived.paces.fast_reps)}</td><td class="num">{fmt_pace(data.derived.paces.fast_reps / 1.609344)}</td></tr>
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
