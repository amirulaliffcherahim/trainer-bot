<script lang="ts">
	let { data } = $props();

	const fmtTime = (min: number) => {
		const s = Math.round(min * 60);
		return `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
	};
	const fmtPace = (sp: number) => {
		const s = Math.round(sp);
		return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
	};
	const dist = (m: number) => (m >= 1000 ? `${Math.round((m / 1000) * 10) / 10} km` : `${Math.round(m)} m`);
	const race = $derived(data.race);
</script>

<svelte:head><title>Race — trainer·bot</title></svelte:head>

{#if !race}
	<div class="card">
		<div class="empty">
			<div class="big">No goal race set</div>
			Add one on the Plan tab (Build/Renew → Goal race) and I'll prep you for it —
			phases, taper, race-day pacing and fueling.
		</div>
		<a class="btn" href="/plan">Go to Plan</a>
	</div>
{:else}
	<div class="hero" style="background:linear-gradient(135deg,#9a3412,#c2410c)">
		<div class="label">🏁 {race.race.category || race.race.name}</div>
		<div class="score" style="font-size:1.8rem">{dist(race.race.distance_m)} · {race.daysTo} days to go</div>
		<div class="src">
			{race.race.name} · {race.race.event_date} ·
			Goal {fmtTime(race.goal.timeMin)} · {fmtPace(race.goal.pace_s_km)}/km
		</div>
	</div>

	<div class="card">
		<h2>Taper & volume</h2>
		{#if race.taper.length > 0}
			<table class="tbl">
				<thead><tr><th>Weeks out</th><th>Volume</th><th>Notes</th></tr></thead>
				<tbody>
					{#each race.taper as t (t.out)}
						<tr>
							<td>{t.out}</td>
							<td>{t.pct}%</td>
							<td>{t.easyOnly ? 'easy only' : 'keep light quality'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="subtle">(volume_progression.md — taper −3 75%, −2 55%, race week 35% easy only. If you're further out, you're in build weeks.)</p>
		{:else}
			<p class="subtle">Race week — you're in the taper already.</p>
		{/if}
	</div>

	<div class="card">
		<h2>Pacing plan</h2>
		{#each race.negativeSplit as l (l)}
			<p class="subtle" style="margin:4px 0">{l}</p>
		{/each}
	</div>

	<div class="card">
		<h2>Fuel & hydrate</h2>
		{#each race.fueling as l (l)}
			<p class="subtle" style="margin:4px 0">• {l}</p>
		{/each}
	</div>

	<div class="card">
		<h2>After the finish line</h2>
		{#each race.postRace as l (l)}
			<p class="subtle" style="margin:4px 0">• {l}</p>
		{/each}
		<p class="subtle">Then pick the next goal on the Plan tab — the plan rebuilds around it.</p>
	</div>
{/if}
