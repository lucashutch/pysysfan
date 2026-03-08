<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { api } from '../lib/api'
  import { daemonStatus, sensorData, sensorHistory, connectionStatus } from '../lib/stores'
  import type { SensorData } from '../lib/types'
  import SensorCard from './sensors/SensorCard.svelte'
  import TempGauge from './sensors/TempGauge.svelte'
  import FanGauge from './sensors/FanGauge.svelte'
  import SensorChart from './sensors/SensorChart.svelte'

  let unsubscribe: (() => void) | null = null
  const MAX_HISTORY = 60

  onMount(async () => {
    try {
      await api.initialize()
      connectionStatus.set('connecting')

      const status = await api.getState()
      daemonStatus.set(status)

      unsubscribe = api.subscribeToSensors((data: SensorData) => {
        sensorData.set(data)
        connectionStatus.set('connected')

        sensorHistory.update(history => {
          const newHistory = { ...history }

          for (const temp of data.temperatures) {
            if (!newHistory.temperatures[temp.identifier]) {
              newHistory.temperatures[temp.identifier] = []
            }
            newHistory.temperatures[temp.identifier].push({
              time: data.timestamp,
              value: temp.value
            })
            if (newHistory.temperatures[temp.identifier].length > MAX_HISTORY) {
              newHistory.temperatures[temp.identifier].shift()
            }
          }

          for (const fan of data.fans) {
            if (!newHistory.fans[fan.identifier]) {
              newHistory.fans[fan.identifier] = []
            }
            newHistory.fans[fan.identifier].push({
              time: data.timestamp,
              value: fan.rpm
            })
            if (newHistory.fans[fan.identifier].length > MAX_HISTORY) {
              newHistory.fans[fan.identifier].shift()
            }
          }

          return newHistory
        })
      })
    } catch (e) {
      connectionStatus.set('disconnected')
      console.error('Failed to connect:', e)
    }
  })

  onDestroy(() => {
    if (unsubscribe) {
      unsubscribe()
    }
  })

  function getControlForFan(fanIdentifier: string, controls: any[]) {
    return controls.find(c => 
      c.hardware_name === 'Motherboard' || 
      c.identifier.includes(fanIdentifier.split('/').slice(0, -1).join('/'))
    )
  }
</script>

<div class="p-4">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-3xl font-bold text-primary">Dashboard</h1>
    <div class="flex items-center gap-2">
      <span class="text-sm opacity-70">Status:</span>
      {#if $connectionStatus === 'connected'}
        <span class="badge badge-success">Connected</span>
      {:else if $connectionStatus === 'connecting'}
        <span class="badge badge-warning">Connecting...</span>
      {:else}
        <span class="badge badge-error">Disconnected</span>
      {/if}
    </div>
  </div>

  {#if $daemonStatus}
    <div class="mb-4 p-4 bg-base-200 rounded-lg">
      <div class="flex flex-wrap gap-4 text-sm">
        <div>
          <span class="opacity-60">PID:</span>
          <span class="font-mono ml-2">{$daemonStatus.pid ?? 'N/A'}</span>
        </div>
        <div>
          <span class="opacity-60">Uptime:</span>
          <span class="font-mono ml-2">
            {#if $daemonStatus.uptime_seconds}
              {Math.floor($daemonStatus.uptime_seconds / 60)}m
            {:else}
              N/A
            {/if}
          </span>
        </div>
        <div>
          <span class="opacity-60">Profile:</span>
          <span class="font-mono ml-2">{$daemonStatus.active_profile}</span>
        </div>
        <div>
          <span class="opacity-60">Poll Interval:</span>
          <span class="font-mono ml-2">{$daemonStatus.poll_interval}s</span>
        </div>
      </div>
    </div>
  {/if}

  {#if $sensorData}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
      <SensorCard title="Temperatures" icon="🌡️">
        <div class="flex flex-wrap gap-4 justify-center">
          {#each $sensorData.temperatures as temp}
            <TempGauge 
              value={temp.value} 
              label={temp.sensor_name}
              min={0}
              max={100}
            />
          {/each}
          {#if $sensorData.temperatures.length === 0}
            <p class="opacity-50 text-sm">No temperature sensors found</p>
          {/if}
        </div>
      </SensorCard>

      <SensorCard title="Fans" icon="🌀">
        <div class="flex flex-wrap gap-4 justify-center">
          {#each $sensorData.fans as fan}
            {@const control = getControlForFan(fan.identifier, $sensorData.controls)}
            <FanGauge 
              rpm={fan.rpm} 
              controllable={control?.has_control ?? false}
              label={fan.sensor_name}
              controlValue={control?.current_value}
            />
          {/each}
          {#if $sensorData.fans.length === 0}
            <p class="opacity-50 text-sm">No fans found</p>
          {/if}
        </div>
      </SensorCard>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {#each Object.entries($sensorHistory.temperatures) as [id, history]}
        <SensorCard title="Temperature History - {id.split('/').pop()}">
          <SensorChart 
            data={history} 
            label="Temperature"
            unit="°C"
            color="#ef4444"
            min={0}
            max={100}
          />
        </SensorCard>
      {/each}

      {#each Object.entries($sensorHistory.fans) as [id, history]}
        <SensorCard title="Fan History - {id.split('/').pop()}">
          <SensorChart 
            data={history} 
            label="RPM"
            unit="RPM"
            color="#3b82f6"
          />
        </SensorCard>
      {/each}
    </div>
  {:else if $connectionStatus === 'connecting'}
    <div class="flex justify-center items-center h-64">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else}
    <div class="alert alert-error">
      <span>Failed to connect to daemon. Make sure it's running.</span>
    </div>
  {/if}
</div>
