<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	let { children } = $props();

	const url = $derived(page.url);
	const tabs = [
		{ href: '/', ic: '🎯', label: 'Today' },
		{ href: '/plan', ic: '📅', label: 'Plan' },
		{ href: '/activities', ic: '🏃', label: 'Activity' },
		{ href: '/fitness', ic: '📈', label: 'Fitness' },
		{ href: '/settings', ic: '⚙️', label: 'Settings' }
	];

	let theme = $state<'light' | 'dark'>('light');

	function apply(t: 'light' | 'dark') {
		theme = t;
		document.documentElement.dataset.theme = t;
		try {
			localStorage.setItem('tb-theme', t);
		} catch {
			/* private mode etc. — ignore */
		}
	}

	onMount(() => {
		let stored: string | null = null;
		try {
			stored = localStorage.getItem('tb-theme');
		} catch {
			/* ignore */
		}
		const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
		apply(stored === 'dark' || stored === 'light' ? stored : prefersDark ? 'dark' : 'light');
	});
</script>

<div class="app">
	<header class="app-head">
		<span class="brand">trainer<span class="dot">·</span>bot</span>
		<span style="display:flex;gap:8px;align-items:center">
			<span class="subtle">coach in your pocket</span>
			<button class="btn ghost" style="width:auto;padding:4px 10px;font-size:.85rem" onclick={() => apply(theme === 'dark' ? 'light' : 'dark')} aria-label="toggle dark mode">
				{theme === 'dark' ? '☀️' : '🌙'}
			</button>
		</span>
	</header>
	{@render children()}
</div>

<nav class="tabbar">
	{#each tabs as tab (tab.href)}
		<a class="tab" href={tab.href} aria-current={url.pathname === tab.href ? 'page' : undefined}>
			<span class="ic">{tab.ic}</span>
			{tab.label}
		</a>
	{/each}
</nav>
