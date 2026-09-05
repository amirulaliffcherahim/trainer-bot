<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
import { fmt_time } from '$lib/vdot';
	let { data } = $props();

	const prettyDate = (iso: string | null | undefined) =>
		iso ? new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '';

	const notice = $derived(page.url.searchParams.get('notice'));
	let syncing = $state(false);
	let syncMsg: string | null = $state(null);

	const KIND: Record<string, string> = {
		easy: 'Easy', quality: 'Threshold', interval: 'Intervals', long: 'Long',
		rest: 'Rest', race: 'Race'
	};
	const distKm = (m: number | null): string =>
		m === null || m <= 0 ? '' : `${Math.round((m / 1000) * 10) / 10} km`;

	/* daily check-in (S3 journal) */
	const journal = $derived(data.journal?.journal ?? null);
	const chk = $state({ energy: '', sleep: '', soreness: '', note: '' });
	let chkSaving = $state(false);
	let chkMsg = $state('');
	const SORE = ['none', 'mild', 'noticeable', 'sharp'];
	async function saveCheckin() {
		chkSaving = true;
		chkMsg = '';
		try {
			const res = await fetch('/api/journal', {
				method: 'PUT',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ energy: chk.energy, sleep_h: chk.sleep, soreness: chk.soreness, note: chk.note })
			});
			if (!res.ok) throw new Error('check-in failed');
			await goto('/');
		} catch (err) {
			chkMsg = err instanceof Error ? err.message : 'check-in failed';
		} finally {
			chkSaving = false;
		}
	}
	const coachLine = $derived((data.plan?.coachNote ?? []).join(' '));

	async function syncNow() {
		syncing = true;
		syncMsg = null;
		try {
			const res = await fetch('/api/sync', { method: 'POST' });
			const body = await res.json();
			if (!res.ok) throw new Error(body.message ?? 'sync failed');
			syncMsg = body.summary;
			// refresh status/fitness shown on this page
			const [s, f] = await Promise.all([
				(await fetch('/api/status')).json(),
				(await fetch('/api/fitness')).json()
			]);
			data.status = s;
			data.fitness = f;
		} catch (err) {
			syncMsg = err instanceof Error ? err.message : 'sync failed';
		} finally {
			syncing = false;
		}
	}

</script>

<svelte:head><title>Today — trainer·bot</title></svelte:head>

{#if notice}
	<div class="notice">{notice}</div>
{/if}

{#if !data.status.configured}
	<div class="card">
		<h2>Almost there — Strava needs an app first</h2>
		<p class="subtle">Register a personal app at <strong>strava.com/settings/api</strong>,
			then set <code>STRAVA_CLIENT_ID</code> and <code>STRAVA_CLIENT_SECRET</code> in a
			local <code>.env</code> (see <code>.env.example</code>). Restart, then come back.</p>
		<a class="btn" href="/settings">Go to Settings</a>
	</div>
{:else if !data.status.connected}
	<div class="card">
		<h2>Connect your Strava</h2>
		<p class="subtle">I’ll pull your activities (read-only), keep an estimated VO₂ max from your
			best efforts, and later build your plan around them.</p>
		<a class="btn sync" href="/api/auth/strava">Connect with Strava</a>
	</div>
{:else}
	{#if data.status.connected && !data.status.can_read_activities}
		<div class="notice">Connected, but Strava only granted <strong>{data.status.scopes}</strong> —
			I can't see your runs yet. <a href="/settings">Reconnect in Settings</a> and allow
			activity access.</div>
	{/if}
	{#if data.fitness?.derived}
		<div class="hero">
			<div class="label">Estimated VO₂ max</div>
			<div class="score">{data.fitness.derived.vdot.toFixed(1)}</div>
			<div class="src">from {data.fitness.snapshot.source_name ?? 'your best effort'}
				· {Math.round(data.fitness.snapshot.source_distance / 1000 * 10) / 10} km
				· {fmt_time(data.fitness.snapshot.source_time_min)}
				· {prettyDate(data.fitness.snapshot.source_date)}</div>
		</div>
	{:else}
		<div class="card">
			<h2>No fitness anchor yet</h2>
			<p class="subtle">After you connect, hit <strong>Sync now</strong> — I look for
				your 5K PR to compute your estimated VO₂ max.</p>
			<button class="btn sync" onclick={syncNow} disabled={syncing}>
				{syncing ? 'Syncing…' : 'Sync now'}
			</button>
			{#if syncMsg}<p class="subtle">{syncMsg}</p>{/if}
		</div>
	{/if}

	<div class="card">
		<h2>Daily check-in</h2>
		{#if journal}
			<p class="subtle">Logged — energy {journal.energy ?? '—'}/5 · sleep {journal.sleep_h ?? '—'} h · soreness {journal.soreness ?? '—'}
				{#if journal.note}<br>{journal.note}{/if}</p>
		{:else}
			<p class="subtle">How's today feeling? This steers what I give you.</p>
			<span class="lbl">Energy</span>
			<div class="chips">
				{#each [1, 2, 3, 4, 5] as n (n)}
					<button class="chip {chk.energy === String(n) ? 'on' : ''}" onclick={() => (chk.energy = String(n))}>{n}</button>
				{/each}
			</div>
			<span class="lbl">Sleep (hours)</span>
			<div class="chips">
				{#each [5, 6, 7, 8, 9] as n (n)}
					<button class="chip {chk.sleep === String(n) ? 'on' : ''}" onclick={() => (chk.sleep = String(n))}>{n}h</button>
				{/each}
			</div>
			<span class="lbl">Soreness</span>
			<div class="chips">
				{#each SORE as s (s)}
					<button class="chip {chk.soreness === s ? 'on' : ''}" onclick={() => (chk.soreness = s)}>{s}</button>
				{/each}
			</div>
			<input class="inp" placeholder="Anything else? (optional)" bind:value={chk.note} style="margin:8px 0" />
			<button class="btn" onclick={saveCheckin} disabled={chkSaving}>{chkSaving ? 'Saving…' : 'Save check-in'}</button>
			{#if chkMsg}<p class="subtle">{chkMsg}</p>{/if}
		{/if}
	</div>

	{#if coachLine}
		<div class="notice"><strong>Coach</strong> · {coachLine}</div>
	{/if}

	<div class="card">
		<h2>Today</h2>
		{#if data.status.activity_count > 0}
			{#if data.plan?.days?.length > 0 && data.plan.days[0].planned.length > 0}
				{#each data.plan.days[0].planned as p (p.session.kind)}
					<div class="row" style="flex-direction:column;align-items:flex-start;gap:4px;border:0">
						<div style="display:flex;gap:8px;align-items:center;width:100%">
							<span style="font-weight:700">
								{KIND[p.session.kind]}{#if p.session.distance_m} · {distKm(p.session.distance_m)}{/if}
							</span>
							{#if p.status === 'done'}<span class="tag ok">Completed</span>
							{:else if p.status === 'partial'}<span class="tag warn">Modified</span>
							{:else if p.status === 'missed'}<span class="tag err">Missed</span>
							{:else if p.status === 'extra'}<span class="tag">Extra run</span>{/if}
						</div>
						{#if p.session.kind !== 'rest'}
							<span class="subtle">{p.session.label}</span>
						{/if}
						<span class="subtle">{p.session.reason}</span>
					</div>
				{/each}
			{:else}
				<div class="empty">
					<div class="big">No plan for today yet</div>
					<a class="btn" style="margin-top:10px" href="/plan">Open Plan & build one</a>
				</div>
			{/if}
			<div style="display:flex;gap:8px;margin-top:8px">
				<button class="btn sync" style="flex:1" onclick={syncNow} disabled={syncing}>
					{syncing ? 'Syncing…' : 'Sync Strava'}
				</button>
				<a class="btn ghost" style="flex:1" href="/plan">Plan</a>
			</div>
			{#if syncMsg}<p class="subtle">{syncMsg}</p>{/if}
		{:else}
			<div class="empty">
				<div class="big">No activities yet</div>
				Run something, then sync.
			</div>
		{/if}
	</div>
{/if}
