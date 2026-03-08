<script lang="ts">
  import { api } from '../lib/api'
  import { onMount } from 'svelte'

  let logs: string[] = []
  let totalLines = 0
  let loading = false
  let error: string | null = null
  let lineCount = 100
  let autoRefresh = false
  let refreshInterval: ReturnType<typeof setInterval> | null = null
  let logContainer: HTMLDivElement

  onMount(() => {
    loadLogs()
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval)
      }
    }
  })

  async function loadLogs() {
    loading = true
    error = null
    try {
      const response = await api.getServiceLogs(lineCount)
      logs = response.logs
      totalLines = response.total_lines
      scrollToBottom()
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load logs'
    } finally {
      loading = false
    }
  }

  function scrollToBottom() {
    if (logContainer) {
      requestAnimationFrame(() => {
        logContainer.scrollTop = logContainer.scrollHeight
      })
    }
  }

  function handleAutoRefresh() {
    if (autoRefresh) {
      refreshInterval = setInterval(loadLogs, 2000)
    } else if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }

  $: if (autoRefresh !== undefined) {
    handleAutoRefresh()
  }

  function handleLineCountChange(event: Event) {
    const target = event.target as HTMLSelectElement
    lineCount = parseInt(target.value)
    loadLogs()
  }
</script>

<div class="card bg-base-200 shadow-md">
  <div class="card-body p-4">
    <div class="flex justify-between items-center mb-2">
      <h2 class="card-title text-base flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        Logs
      </h2>
      <div class="flex items-center gap-2">
        <select class="select select-bordered select-xs" value={lineCount} onchange={handleLineCountChange}>
          <option value={50}>50 lines</option>
          <option value={100}>100 lines</option>
          <option value={200}>200 lines</option>
          <option value={500}>500 lines</option>
        </select>
        <label class="flex items-center gap-1 text-xs cursor-pointer">
          <input type="checkbox" class="checkbox checkbox-xs" bind:checked={autoRefresh} />
          Auto
        </label>
        <button class="btn btn-xs btn-ghost" onclick={loadLogs} disabled={loading}>
          {#if loading}
            <span class="loading loading-spinner loading-xs"></span>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          {/if}
        </button>
      </div>
    </div>

    {#if error}
      <div class="alert alert-error text-sm py-2">
        <span>{error}</span>
      </div>
    {:else}
      <div
        bind:this={logContainer}
        class="bg-base-300 rounded p-2 font-mono text-xs h-48 overflow-y-auto"
      >
        {#if loading && logs.length === 0}
          <div class="flex justify-center items-center h-full">
            <span class="loading loading-spinner loading-sm"></span>
          </div>
        {:else if logs.length === 0}
          <span class="opacity-50">No logs available</span>
        {:else}
          {#each logs as line, i}
            <div class="flex">
              <span class="opacity-40 w-8 text-right pr-2 select-none">{i + 1}</span>
              <span class="whitespace-pre-wrap break-all">{line}</span>
            </div>
          {/each}
        {/if}
      </div>

      <div class="text-xs opacity-50 mt-1">
        Showing {logs.length} of {totalLines} lines
      </div>
    {/if}
  </div>
</div>
