<script lang="ts">
	let { data } = $props();

	const WDAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
	const psec = (s: number | null) =>
		s === null ? '' : `${Math.floor(Math.round(s) / 60)}:${String(Math.round(s) % 60).padStart(2, '0')}`;
	const dist = (m: number) => (m >= 1000 ? `${Math.round((m / 1000) * 10) / 10} km` : `${Math.round(m)} m`);
	const day = (iso: string | null) => {
		if (!iso) return '';
		const d = new Date(iso);
		return `${WDAY[d.getDay()]}, ${d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`;
	};

	const FELT = ['easy', 'on target', 'hard'];
	const SORE = ['none', 'mild', 'noticeable', 'sharp'];

	let openId = $state<number | null>(null);
	let saving = $state(false);
	let savedMsg = $state('');
	const form = $state({ id: 0, rpe: '', felt: '', soreness: '', note: '' });

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	function openAct(a: any) {
		if (openId === a.strava_id) {
			openId = null;
			return;
		}
		openId = a.strava_id;
		form.id = a.strava_id;
		form.rpe = a.feedback?.rpe != null ? String(a.feedback.rpe) : '';
		form.felt = a.feedback?.felt ?? '';
		form.soreness = a.feedback?.soreness ?? '';
		form.note = a.feedback?.note ?? '';
		savedMsg = '';
	}

	async function save() {
		saving = true;
		savedMsg = '';
		try {
			const res = await fetch('/api/activities', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ strava_id: form.id, rpe: form.rpe, felt: form.felt, soreness: form.soreness, note: form.note })
			});
			if (!res.ok) throw new Error('save failed');
			data = await (await fetch('/api/activities')).json();
			savedMsg = 'Saved. Thanks — that steers tomorrow.';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head><title>Activity — trainer·bot</title></svelte:head>

<div class="card">
	<h2>Activity & AI review</h2>
	<p class="subtle">{data.activities.length} recent sessions — open one for the review and log how it felt.
		{#if !data.has_vdot}<br><strong>No VDOT anchor yet</strong> — reviews show once an anchor exists.{/if}</p>
</div>

{#if data.activities.length === 0}
	<div class="empty"><div class="big">Nothing here yet</div>Connect Strava and sync (Settings → Sync now).</div>
{/if}

{#each data.activities as a (a.strava_id)}
	<div class="card" style="padding:12px 14px">
		<button class="row" style="width:100%;border:0;background:none;cursor:pointer;text-align:left;padding:0" onclick={() => openAct(a)}>
			<span>
				<span style="font-weight:700">{a.name}</span><br>
				<span class="subtle">{day(a.start_date_local)} · {dist(a.distance)}
					{#if a.pace_sec_km} · {psec(a.pace_sec_km)}/km{/if}
					{#if a.average_heartrate} · ❤ {Math.round(a.average_heartrate)}{/if}
				</span>
			</span>
			{#if a.feedback}<span class="tag ok">rated {a.feedback.rpe ? a.feedback.rpe + '/10' : a.feedback.felt}</span>
			{:else}<span class="tag warn">needs feedback</span>{/if}
		</button>

		{#if openId === a.strava_id}
			<div style="border-top:1px solid var(--line);margin-top:10px;padding-top:10px">
				{#if a.review}
					<p style="margin:0 0 6px"><strong>{a.review.headline}</strong></p>
					{#each a.review.points as pt (pt)}
						<p class="subtle" style="margin:2px 0">{pt}</p>
					{/each}
				{/if}

				<div style="margin-top:10px">
					<span class="lbl">How did it feel?</span>
					<div class="chips">
						{#each FELT as fl (fl)}
							<button class="chip {form.felt === fl ? 'on' : ''}" onclick={() => (form.felt = fl)}>{fl}</button>
						{/each}
					</div>
					<span class="lbl">Effort (RPE 1–10)</span>
					<div class="chips">
						{#each [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as n (n)}
							<button class="chip {form.rpe === String(n) ? 'hard' : ''}" onclick={() => (form.rpe = String(n))}>{n}</button>
						{/each}
					</div>
					<span class="lbl">Soreness after</span>
					<div class="chips">
						{#each SORE as s (s)}
							<button class="chip {form.soreness === s ? 'on' : ''}" onclick={() => (form.soreness = s)}>{s}</button>
						{/each}
					</div>
					<input class="inp" placeholder="Note (optional) — weather, route, how you woke up…" bind:value={form.note} style="margin:8px 0" />
					<button class="btn" onclick={save} disabled={saving}>{saving ? 'Saving…' : a.feedback ? 'Update feedback' : 'Save feedback'}</button>
					{#if savedMsg}<p class="subtle">{savedMsg}</p>{/if}
				</div>
			</div>
		{/if}
	</div>
{/each}
