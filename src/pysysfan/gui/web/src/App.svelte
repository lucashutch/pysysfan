<script lang="ts">
  import { onMount } from 'svelte'
  import Dashboard from './components/pages/Dashboard.svelte'
  import { connectionStatus } from './lib/stores'
  import { api } from './lib/api'

  let loading = true
  let error: string | null = null

  onMount(async () => {
    try {
      await api.initialize()
      connectionStatus.set('connected')
      loading = false
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error'
      connectionStatus.set('disconnected')
      loading = false
    }
  })
</script>

<main class="min-h-screen bg-base-100">
  {#if loading}
    <div class="flex justify-center items-center h-64">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else if error}
    <div class="p-4">
      <div class="alert alert-error">
        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        <span>{error}</span>
      </div>
    </div>
  {:else}
    <Dashboard />
  {/if}
</main>
