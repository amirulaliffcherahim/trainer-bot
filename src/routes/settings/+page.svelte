<script lang="ts">
	import { goto } from '$app/navigation';
	let { data } = $props();

	let busy = $state(false);
	let msg: string | null = $state(null);

	async function syncNow() {
		busy = true;
		msg = null;
		try {
			const res = await fetch('/api/sync', { method: 'POST' });
			const body = await res.json();
			if (!res.ok) throw new Error(body.message ?? 'sync failed');
			msg = body.summary;
		} catch (err) {
			msg = err instanceof Error ? err.message : 'sync failed';
		} finally {
			busy = false;
		}
	}

	async function disconnect() {
		busy = true;
		try {
			await fetch('/api/auth/disconnect', { method: 'POST' });
			await goto('/settings', { invalidateAll: true });
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>Settings — trainer·bot</title></svelte:head>

<div class="card">
	<h2>Strava</h2>
	<div class="row"><span class="k">App configured</span>
		{#if data.configured}<span class="tag ok">yes</span>{:else}<span class="tag err">no</span>{/if}
	</div>
	<div class="row"><span class="k">Connected</span>
		{#if data.connected}
		<span class="tag ok">yes{data.connected_athlete ? ' — ' + data.connected_athlete : ''}</span>
		{:else}
			<span class="tag warn">not yet</span>
		{/if}
	</div>
	{#if data.connected}
		<div class="row"><span class="k">Scopes granted</span>
			{#if data.can_read_activities}
				<span class="tag ok">{data.scopes}</span>
			{:else}
				<span class="tag err">{data.scopes}</span>
			{/if}
		</div>
		<div class="row"><span class="k">Activities stored</span><span class="k">{data.activity_count}</span></div>
	{/if}
	<div style="height:10px"></div>
	{#if !data.configured}
		<div class="notice">Create a personal app at strava.com/settings/api, then add
			<code>STRAVA_CLIENT_ID</code> + <code>STRAVA_CLIENT_SECRET</code> to a local
			<code>.env</code> file (copy <code>.env.example</code>) and restart the server.</div>
	{:else if !data.connected}
		<a class="btn sync" href="/api/auth/strava">Connect with Strava</a>
	{:else if !data.can_read_activities}
		<div class="notice"><strong>Connected, but missing activity access.</strong>
			Your earlier consent only granted <code>{data.scopes}</code> — trainer-bot can't see
			your runs yet. Reconnect and tick <em>activity</em> (read) on Strava's page to fix it.
		</div>
		<a class="btn sync" href="/api/auth/strava">Reconnect — request activity access</a>
		<div style="height:8px"></div>
		<button class="btn ghost" onclick={disconnect} disabled={busy}>Disconnect</button>
	{:else}
		<button class="btn sync" onclick={syncNow} disabled={busy}>{busy ? 'Syncing…' : 'Sync now'}</button>
		<div style="height:8px"></div>
		<button class="btn ghost" onclick={disconnect} disabled={busy}>Disconnect</button>
	{/if}
	{#if msg}<p class="subtle">{msg}</p>{/if}
</div>

<div class="card">
	<h2>About</h2>
	<p class="subtle">Single-user trainer. Data lives in a local SQLite file
		(<code>trainer.db</code>). VDOT math is a port of the vdoto2.com engine —
		see <code>knowledge/vdot_engine/</code>. Product design threads live in
		<code>planning/</code>.</p>
</div>
