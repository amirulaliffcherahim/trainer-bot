<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	let { children } = $props();

	/* stroke glyphs, 24px grid, currentColor */
	const ICONS: Record<string, string> = {
		home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.2 12 3.8l9 7.4"/><path d="M5.4 9.9V20h5.1v-5.4h3V20h5.1V9.9"/></svg>`,
		calendar: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><rect x="3.4" y="5.2" width="17.2" height="15.2" rx="2.4"/><path d="M3.4 9.8h17.2"/><path d="M8 3.2v3.6M16 3.2v3.6"/></svg>`,
		activity: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 13h4.2l2.7-6.4 4 12.8 3.1-7.4h5"/></svg>`,
		trend: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 17.5l6-6 4 4 8.5-8.5"/><path d="M14.5 7h6.5v6.5"/></svg>`,
		gear: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94s-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87a.49.49 0 0 0 .12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.61l-2.03-1.58zM12 15.6a3.6 3.6 0 1 1 0-7.2 3.6 3.6 0 0 1 0 7.2z"/></svg>`,
		sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7"/></svg>`,
		moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20.4 14.2A8.4 8.4 0 0 1 9.8 3.6a8.5 8.5 0 1 0 10.6 10.6z"/></svg>`
	};

	const url = $derived(page.url);
	const tabs = [
		{ href: '/', ic: ICONS.home, label: 'Today' },
		{ href: '/plan', ic: ICONS.calendar, label: 'Plan' },
		{ href: '/activities', ic: ICONS.activity, label: 'Activity' },
		{ href: '/fitness', ic: ICONS.trend, label: 'Fitness' },
		{ href: '/settings', ic: ICONS.gear, label: 'Settings' }
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
		<button class="btn ghost iconbtn" onclick={() => apply(theme === 'dark' ? 'light' : 'dark')}
			aria-label={theme === 'dark' ? 'switch to light mode' : 'switch to dark mode'}>
			{@html theme === 'dark' ? ICONS.sun : ICONS.moon}
		</button>
	</header>
	{@render children()}
</div>

<nav class="tabbar">
	{#each tabs as tab (tab.href)}
		<a class="tab" href={tab.href} aria-current={url.pathname === tab.href ? 'page' : undefined}>
			<span class="ic">{@html tab.ic}</span>
			{tab.label}
		</a>
	{/each}
</nav>
