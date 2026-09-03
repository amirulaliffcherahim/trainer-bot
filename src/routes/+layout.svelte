<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	let { children } = $props();
	const url = $derived(page.url);
	const tabs = [
		{ href: '/', ic: '🎯', label: 'Today' },
		{ href: '/plan', ic: '📅', label: 'Plan' },
		{ href: '/activities', ic: '🏃', label: 'Activity' },
		{ href: '/fitness', ic: '📈', label: 'Fitness' },
		{ href: '/settings', ic: '⚙️', label: 'Settings' }
	];
</script>

<div class="app">
	<header class="app-head">
		<span class="brand">trainer<span class="dot">·</span>bot</span>
		<span class="subtle">coach in your pocket</span>
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
