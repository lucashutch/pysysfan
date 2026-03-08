<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api'
  import type { ServiceStatus } from '../lib/types'
  import ServiceStatusComponent from '../service/ServiceStatus.svelte'
  import StopButton from '../service/StopButton.svelte'
  import LogViewer from '../service/LogViewer.svelte'

  let serviceStatus: ServiceStatus | null = null
  let loading = false
  let error: string | null = null
  let toastMessage: string | null = null

  onMount(() => {
    refreshStatus()
  })

  async function refreshStatus() {
    loading = true
    error = null
    try {
      serviceStatus = await api.getServiceStatus()
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to get service status'
    } finally {
      loading = false
    }
  }

  function showToast(message: string) {
    toastMessage = message
    setTimeout(() => {
      toastMessage = null
    }, 3000)
  }

  function handleServiceEvent() {
    refreshStatus()
    showToast('Service status updated')
  }

  function handleStopError(e: CustomEvent<string>) {
    showToast(`Error: ${e.detail}`)
  }

  function handleStopped(e: CustomEvent<{ method: string }>) {
    refreshStatus()
    showToast(`Daemon stopped via ${e.detail.method}`)
  }
</script>

<div class="p-4 max-w-4xl mx-auto">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-3xl font-bold text-primary">Settings</h1>
  </div>

  {#if toastMessage}
    <div class="toast toast-top toast-end">
      <div class="alert alert-info">
        <span>{toastMessage}</span>
      </div>
    </div>
  {/if}

  {#if error}
    <div class="alert alert-error mb-4">
      <span>{error}</span>
      <button class="btn btn-sm" onclick={refreshStatus}>Retry</button>
    </div>
  {/if}

  <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
    <div>
      <ServiceStatusComponent
        bind:status={serviceStatus}
        bind:loading
        on:refresh={refreshStatus}
        on:install={handleServiceEvent}
        on:uninstall={handleServiceEvent}
        on:enable={handleServiceEvent}
        on:disable={handleServiceEvent}
        on:start={handleServiceEvent}
      />
    </div>

    {#if serviceStatus?.daemon_running}
      <div>
        <StopButton
          on:stopped={handleStopped}
          on:error={handleStopError}
        />
      </div>
    {/if}
  </div>

  <div class="grid grid-cols-1 gap-4">
    <LogViewer />
  </div>
</div>
