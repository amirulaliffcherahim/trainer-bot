<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';

	let { data } = $props();

	const WDAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
	

	const KIND: Record<string, string> = {
		easy: 'Easy', quality: 'Threshold', interval: 'Intervals', long: 'Long',
		rest: 'Rest', race: 'Race'
	};
	const psec = (s: number | null) =>
		s === null ? '' : `${Math.floor(Math.round(s) / 60)}:${String(Math.round(s) % 60).padStart(2, '0')}`;
	const wd = (d: string) => WDAY[new Date(d + 'T00:00:00').getDay()];
	const pretty = (d: string) => new Date(d + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
	const dist = (m: number | null) => (m === null || m <= 0 ? '' : m >= 1000 ? `${Math.round((m / 1000) * 10) / 10} km` : `${Math.round(m)} m`);
	const daysTo = (date: string) => {
		const a = new Date(); a.setHours(0, 0, 0, 0);
		return Math.round((new Date(date + 'T00:00:00').getTime() - a.getTime()) / 86400000);
	};

	const notice = $derived(page.url.searchParams.get('notice'));
	const activeEvent = $derived(data.events.find((e: { event_date: string }) => e.event_date >= new Date().toISOString().slice(0, 10)));

	/* ---- wizard state (always asked on build/renew) ---- */
	const hadPlan = data.days.length > 0;
	const initRun = data.prefs?.runDays?.length ? [...data.prefs.runDays] : [1, 2, 4, 5, 6];
	const initKinds: Record<number, string> = data.prefs?.kinds ? { ...data.prefs.kinds } : {};
	let open = $state(!hadPlan);
	const prefs = $state({
		runDays: initRun,
		kinds: initKinds as Record<number, string>
	});
	let busy = $state(false);
	let msg: string | null = $state(null);

	const KIND_OPTIONS = ['easy', 'quality', 'interval', 'long'];
	const KIND_LABEL: Record<string, string> = {
		easy: 'Easy', quality: 'Tempo', interval: 'Speed', long: 'Long'
	};
	const kindOf = (d: number) => prefs.kinds[d] ?? '';
	const hardOf = (d: number) => ['quality', 'interval'].includes(kindOf(d));
	const sortedRun = $derived([...prefs.runDays].sort((a, b) => (a === 0 ? 7 : a) - (b === 0 ? 7 : b)));

	function toggleRun(d: number) {
		if (prefs.runDays.includes(d)) {
			prefs.runDays = prefs.runDays.filter((x) => x !== d);
			delete prefs.kinds[d];
		} else {
			prefs.runDays = [...prefs.runDays, d];
		}
	}
	function setKind(d: number, k: string) {
		if (k === kindOf(d)) delete prefs.kinds[d];
		else prefs.kinds[d] = k;
	}
	async function swapSession(planDate: string, kind: string) {
		busy = true;
		try {
			const res = await fetch('/api/plan/session', {
				method: 'PUT',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ plan_date: planDate, kind })
			});
	if (res.ok) data = await (await fetch('/api/plan')).json();
		} finally {
			busy = false;
		}
	}

	/* ---- race/event form ---- */
	let evName = $state('');
	let evDate = $state('');
	let evKm = $state('');
	let evCat = $state('');
	let evTarget = $state('');
	let evErr: string | null = $state(null);

	async function addRace() {
		evErr = null;
		try {
			const res = await fetch('/api/events', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({
					name: evName,
					distance_m: Number(evKm) * 1000,
					event_date: evDate,
					category: evCat || null,
					target_time_min: evTarget ? Number(evTarget) : null
				})
			});
			const body = await res.json();
			if (!res.ok) throw new Error(body.message ?? 'could not add race');
			evName = evDate = evKm = evCat = evTarget = '';
			data = await (await fetch('/api/plan')).json();
		} catch (err) {
			evErr = err instanceof Error ? err.message : 'could not add race';
		}
	}

	/* ---- build: prefs first, then plan ---- */
	async function build() {
		busy = true;
		msg = null;
		try {
			if (prefs.runDays.length < 2) throw new Error('pick at least 2 training days');
			const hardDays = sortedRun.filter((d) => hardOf(d));
			const prefsRes = await fetch('/api/plan/prefs', {
				method: 'PUT',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ runDays: prefs.runDays, hardDays, kinds: prefs.kinds })
			});
			if (!prefsRes.ok) throw new Error((await prefsRes.json()).message ?? 'could not save preferences');
			const genRes = await fetch('/api/plan/generate', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ horizonDays: 14 }) });
			const body = await genRes.json();
			if (!genRes.ok) throw new Error(body.message ?? 'generate failed');
			data = body;
			open = false;
			msg = 'Plan built from your answers.';
		} catch (err) {
			msg = err instanceof Error ? err.message : 'build failed';
		} finally {
			busy = false;
		}
	}

	const paceBand = (s: { pace_min_s_km: number | null; pace_max_s_km: number | null }) => {
		if (s.pace_min_s_km === null) return '';
		const a = psec(s.pace_min_s_km);
		const b = psec(s.pace_max_s_km ?? s.pace_min_s_km);
		return a === b ? a : `${b}–${a}`;
	};

	async function removeEvent(id: number) {
		await fetch(`/api/events?id=${id}`, { method: 'DELETE' });
		data = await (await fetch('/api/plan')).json();
	}
</script>

<svelte:head><title>Plan — trainer·bot</title></svelte:head>

{#if notice}<div class="notice">{notice}</div>{/if}

{#if activeEvent}
	<div class="card racebanner">
		<div class="raceb-top">
			<h2 style="margin:0">{activeEvent.category || activeEvent.name}</h2>
			{#if activeEvent.id}
				<div style="display:flex;gap:6px">
					<a class="btn" style="width:auto;padding:6px 12px;font-size:.8rem" href="/race">Race prep</a>
					<button class="btn ghost iconbtn" style="padding:6px" onclick={() => removeEvent(activeEvent.id)} aria-label="remove race">✕</button>
				</div>
			{/if}
		</div>
		<p class="subtle" style="margin:6px 0 0">
			{activeEvent.name || 'Goal race'} · {dist(activeEvent.distance_m)} · {daysTo(activeEvent.event_date)} days to go
			{#if activeEvent.target_time_min}· target {Math.floor(activeEvent.target_time_min / 60)}:{String(Math.round(activeEvent.target_time_min % 60)).padStart(2, '0')}{/if}
			{#if !data.hasVdot} · no VO₂ anchor yet{/if}
		</p>
	</div>
{/if}

<div class="card">
	<div style="display:flex;justify-content:space-between;align-items:center">
		<h2 style="margin:0">{data.days.length ? 'Your week' : 'No plan yet'}</h2>
		<button class="btn ghost" style="width:auto;padding:8px 14px" onclick={() => (open = !open)}>
			{open ? 'Close' : data.days.length ? 'Renew my plan' : 'Build my plan'}
		</button>
	</div>

	{#if open}
		<div style="border-top:1px solid var(--line);margin-top:8px;padding-top:6px">
			<p class="subtle">Tell me how your week looks and I'll fit the plan to it.</p>

			<span class="lbl">Training days — {prefs.runDays.length} per week</span>
			<div class="chips">
				{#each [1, 2, 3, 4, 5, 6, 0] as d (d)}
					<button class="chip {prefs.runDays.includes(d) ? 'on' : ''}" onclick={() => toggleRun(d)}>
						{WDAY[d]}
					</button>
				{/each}
			</div>

			<span class="lbl">What each day is (tap to change — Auto = my call)</span>
			{#each sortedRun as d (d)}
				<div style="display:flex;align-items:center;gap:6px;margin:4px 0">
					<span style="width:56px;font-weight:600">{WDAY[d]}</span>
					<button class="chip {!kindOf(d) ? 'on' : ''}" onclick={() => setKind(d, '')}>Auto</button>
					{#each KIND_OPTIONS as k (k)}
						<button class="chip {kindOf(d) === k ? 'on' : ''}" onclick={() => setKind(d, k)}>
							{KIND_LABEL[k]}
						</button>
					{/each}
				</div>
			{/each}
			<p class="subtle" style="margin-top:6px">Leave days on <strong>Auto</strong> and I'll use sensible defaults (tempo on the first hard day, long run on the free Saturday, Wed/Sun rest unless you picked them).</p>

			<span class="lbl">Goal race (optional) — category & date</span>
			<div style="display:flex;flex-direction:column;gap:8px;margin-top:6px">
				<div style="display:flex;gap:8px;flex-wrap:wrap">
					<input class="inp" placeholder="Name (e.g. KL Marathon)" bind:value={evName} style="flex:1.4;min-width:180px" />
					<input class="inp" placeholder="Category (5K / HM…)" bind:value={evCat} style="flex:1;min-width:120px" />
				</div>
				<input class="inp" type="date" bind:value={evDate} style="width:100%" />
				<div style="display:flex;gap:8px;flex-wrap:wrap">
					<input class="inp" inputmode="decimal" placeholder="distance km" bind:value={evKm} style="flex:1;min-width:110px" />
					<input class="inp" inputmode="numeric" placeholder="target min (optional)" bind:value={evTarget} style="flex:1;min-width:150px" />
				</div>
				{#if evErr}<p class="subtle">{evErr}</p>{/if}
				<button class="btn ghost" style="width:auto" onclick={addRace} disabled={!evName || !evDate || !evKm}>Add race</button>
			</div>

			<button class="btn" style="margin-top:12px" onclick={build} disabled={busy || prefs.runDays.length < 2}>
				{busy ? 'Building…' : data.days.length ? 'Renew plan with these' : 'Build my plan'}
			</button>
			{#if msg}<p class="subtle">{msg}</p>{/if}
		</div>
	{/if}
</div>

{#if data.days.length > 0}
	<div class="card">
		<div class="calhead">
			<p class="subtle" style="margin:0"><strong style="color:var(--ink)">Your plan</strong>
				{#if data.horizon?.isRace}
					· race build · {data.horizon.name ?? 'goal race'} · {data.horizon.daysTo} days to go
				{:else}
					· this month · until {pretty(data.horizon?.to)}
				{/if}
			</p>
			<p class="subtle" style="margin:0">anchor {data.anchorKm} km/wk{activeEvent ? '' : ' · grow ≤10%/wk'}</p>
		</div>
		{#each data.days as day (day.date)}
			<div class="dayrow">
				<div class="dayrow-main">
					<div class="daydate">
						<span class="dow">{wd(day.date)}</span>
						<span class="subtle dsub">{pretty(day.date)}</span>
					</div>
					<div class="dmain">
						{#each day.planned as p (day.date + p.session.kind)}
							<div class="dline">
								<span class="dkind">{KIND[p.session.kind] ?? p.session.kind}</span>
								{#if dist(p.session.distance_m)} <span class="subtle">{dist(p.session.distance_m)}</span>{/if}
								{#if paceBand(p.session)} <span class="tag">{paceBand(p.session)}/km</span>{/if}
								{#if p.session.kind === 'rest'} <span class="subtle">· {p.session.reason}</span>{/if}
							</div>
						{/each}
					</div>
					<div class="dstatus">
						{#each day.planned as p (day.date + p.session.kind + 'st')}
							{#if p.status === 'done'}<span class="tag ok">Completed</span>
							{:else if p.status === 'partial'}<span class="tag warn">Modified</span>
							{:else if p.status === 'missed'}<span class="tag err">Missed</span>
							{:else if p.status === 'extra'}<span class="tag">Extra run</span>{/if}
						{/each}
					</div>
				</div>
				{#if day.planned[0] && day.planned[0].session.kind !== 'rest' && day.planned[0].session.kind !== 'race'}
					<div class="chips swapchips">
						{#each KIND_OPTIONS as k (day.date + k)}
							<button class="chip sm {day.planned[0].session.kind === k ? 'on' : ''}" onclick={() => swapSession(day.date, k)} disabled={busy}>
								{KIND_LABEL[k]}
							</button>
						{/each}
					</div>
				{/if}
				{#if day.extras.length > 0}
					<div class="subtle dayextra">
						+ {day.extras.map((x: { distance: number }) => dist(x.distance)).join(' · ')} extra run{day.extras.length > 1 ? 's' : ''}
					</div>
				{/if}
			</div>
		{/each}
	</div>
{:else}
	<div class="empty"><div class="big">No plan yet</div>Hit <strong>Build my plan</strong> — I'll ask about your week and any goal race first.</div>
{/if}
