<script lang="ts">
  import { api } from '../lib/api'
  import type { ServiceStatus } from '../lib/types'
  import { createEventDispatcher } from 'svelte'

  export let status: ServiceStatus | null = null
  export let loading: boolean = false

  const dispatch = createEventDispatcher<{
    refresh: void
    install: void
    uninstall: void
    enable: void
    disable: void
    start: void
  }>()

  async function handleInstall() {
    loading = true
    try {
      await api.installService()
      dispatch('install')
    } finally {
      loading = false
    }
  }

  async function handleUninstall() {
    if (!confirm('Uninstall the service? This will remove the scheduled task.')) {
      return
    }
    loading = true
    try {
      await api.uninstallService()
      dispatch('uninstall')
    } finally {
      loading = false
    }
  }

  async function handleEnable() {
    loading = true
    try {
      await api.enableService()
      dispatch('enable')
    } finally {
      loading = false
    }
  }

  async function handleDisable() {
    loading = true
    try {
      await api.disableService()
      dispatch('disable')
    } finally {
      loading = false
    }
  }

  async function handleStart() {
    loading = true
    try {
      await api.startService()
      dispatch('start')
    } finally {
      loading = false
    }
  }

  function formatLastRun(lastRun: string | null): string {
    if (!lastRun) return 'Never'
    try {
      const date = new Date(lastRun)
      return date.toLocaleString()
    } catch {
      return lastRun
    }
  }

  function getUIState(s: ServiceStatus | null): string {
    if (!s) return 'unknown'
    if (!s.task_installed) return 'not_installed'
    if (!s.task_enabled) return 'disabled'
    if (!s.daemon_running) return 'stopped'
    if (s.daemon_running && s.daemon_healthy) return 'running'
    if (s.daemon_running && !s.daemon_healthy) return 'unhealthy'
    return 'unknown'
  }

  $: uiState = getUIState(status)
</script>

<div class="card bg-base-200 shadow-md">
  <div class="card-body">
    <h2 class="card-title flex items-center gap-2">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M12 5l7 7-7 7" />
      </svg>
      Service Status
    </h2>

    {#if loading}
      <div class="flex justify-center py-4">
        <span class="loading loading-spinner loading-md"></span>
      </div>
    {:else if !status}
      <div class="flex justify-center py-4">
        <span class="text-sm opacity-50">Loading status...</span>
      </div>
    {:else}
      <div class="space-y-3">
        <div class="flex flex-wrap gap-4 text-sm">
          <div class="flex items-center gap-2">
            <span class="opacity-60">Task:</span>
            {#if status.task_installed}
              <span class="badge badge-success">Installed</span>
            {:else}
              <span class="badge badge-ghost">Not Installed</span>
            {/if}
          </div>

          {#if status.task_installed}
            <div class="flex items-center gap-2">
              <span class="opacity-60">Enabled:</span>
              {#if status.task_enabled}
                <span class="badge badge-success">Yes</span>
              {:else}
                <span class="badge badge-error">No</span>
              {/if}
            </div>

            <div class="flex items-center gap-2">
              <span class="opacity-60">Status:</span>
              <span class="font-mono">{status.task_status ?? 'N/A'}</span>
            </div>

            <div class="flex items-center gap-2">
              <span class="opacity-60">Last Run:</span>
              <span class="font-mono text-xs">{formatLastRun(status.task_last_run)}</span>
            </div>
          {/if}
        </div>

        <div class="divider my-1"></div>

        <div class="flex flex-wrap gap-4 text-sm">
          <div class="flex items-center gap-2">
            <span class="opacity-60">Daemon:</span>
            {#if status.daemon_running}
              {#if status.daemon_healthy}
                <span class="badge badge-success">Running</span>
              {:else}
                <span class="badge badge-warning">Running (Unhealthy)</span>
              {/if}
            {:else}
              <span class="badge badge-ghost">Stopped</span>
            {/if}
          </div>

          {#if status.daemon_pid}
            <div class="flex items-center gap-2">
              <span class="opacity-60">PID:</span>
              <span class="font-mono">{status.daemon_pid}</span>
            </div>
          {/if}
        </div>

        <div class="divider my-1"></div>

        <div class="flex flex-wrap gap-2">
          {#if uiState === 'not_installed'}
            <button class="btn btn-primary btn-sm" onclick={handleInstall} disabled={loading}>
              Install Service
            </button>
          {:else if uiState === 'disabled'}
            <button class="btn btn-primary btn-sm" onclick={handleEnable} disabled={loading}>
              Enable Service
            </button>
            <button class="btn btn-error btn-outline btn-sm" onclick={handleUninstall} disabled={loading}>
              Uninstall
            </button>
          {:else if uiState === 'stopped'}
            <button class="btn btn-primary btn-sm" onclick={handleStart} disabled={loading}>
              Start Now
            </button>
            <button class="btn btn-error btn-outline btn-sm" onclick={handleDisable} disabled={loading}>
              Disable
            </button>
          {:else if uiState === 'running'}
            <button class="btn btn-sm" onclick={() => dispatch('refresh')}>
              Refresh
            </button>
          {:else if uiState === 'unhealthy'}
            <div class="alert alert-warning text-sm py-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>Daemon is running but not responding to API</span>
            </div>
            <button class="btn btn-sm" onclick={() => dispatch('refresh')}>
              Refresh
            </button>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>
