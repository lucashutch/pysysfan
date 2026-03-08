<script lang="ts">
  import { api } from '../lib/api'
  import { createEventDispatcher } from 'svelte'

  const dispatch = createEventDispatcher<{
    stopped: { method: string }
    error: string
  }>()

  let stopping = false
  let stopMethod: string | null = null

  async function handleStop() {
    if (!confirm('Stop the daemon? Fans will return to BIOS control.')) {
      return
    }

    stopping = true
    stopMethod = null

    try {
      const response = await api.stopService()
      stopMethod = response.method ?? 'unknown'

      dispatch('stopped', { method: stopMethod })
    } catch (e) {
      dispatch('error', e instanceof Error ? e.message : 'Failed to stop daemon')
    } finally {
      stopping = false
    }
  }
</script>

<div class="flex flex-col gap-2">
  <button
    class="btn btn-error"
    onclick={handleStop}
    disabled={stopping}
  >
    {#if stopping}
      <span class="loading loading-spinner loading-sm"></span>
      Stopping...
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
      </svg>
      Stop Daemon
    {/if}
  </button>

  {#if stopMethod}
    <p class="text-sm opacity-70">
      Stopped via: <code class="bg-base-300 px-1 rounded">{stopMethod}</code>
    </p>
  {/if}
</div>
