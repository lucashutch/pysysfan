<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import type { FanSensor } from '../lib/types'

  export let fan: FanSensor
  export let availableCurves: string[] = ['silent', 'balanced', 'performance']
  export let selectedCurve: string = 'balanced'

  const dispatch = createEventDispatcher<{
    curveChange: { curve: string }
  }>()

  function handleCurveChange(event: Event) {
    const target = event.target as HTMLSelectElement
    dispatch('curveChange', { curve: target.value })
  }

  $: isControllable = fan.controllable ?? false
</script>

<div class="fan-selector" class:read-only={!isControllable}>
  <div class="fan-info">
    <span class="fan-name">{fan.sensor_name}</span>
    {#if isControllable}
      <span class="badge badge-primary">Controllable</span>
    {:else}
      <span class="badge badge-ghost">Read-only</span>
    {/if}
  </div>

  <div class="fan-details">
    <span class="rpm">{fan.rpm} RPM</span>
    {#if fan.control_percentage !== undefined}
      <span class="control-value">{fan.control_percentage}%</span>
    {/if}
  </div>

  {#if isControllable}
    <div class="curve-selector">
      <label class="label" for="curve-{fan.identifier}">
        <span class="label-text">Curve</span>
      </label>
      <select
        id="curve-{fan.identifier}"
        class="select select-bordered select-sm"
        value={selectedCurve}
        on:change={handleCurveChange}
      >
        {#each availableCurves as curve}
          <option value={curve}>{curve}</option>
        {/each}
      </select>
    </div>
  {:else}
    <div class="readonly-note">
      <span class="text-sm opacity-60">Monitoring only</span>
    </div>
  {/if}
</div>

<style>
  .fan-selector {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1rem;
    background: var(--color-base-200);
    border-radius: 8px;
    border: 1px solid var(--color-base-300);
    transition: opacity 0.2s ease;
  }

  .fan-selector.read-only {
    opacity: 0.6;
  }

  .fan-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .fan-name {
    font-weight: 600;
  }

  .fan-details {
    display: flex;
    gap: 1rem;
    font-size: 0.875rem;
    color: var(--color-base-content);
    opacity: 0.8;
  }

  .rpm {
    font-family: monospace;
  }

  .control-value {
    font-family: monospace;
  }

  .curve-selector {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .curve-selector .label {
    margin-bottom: 0;
  }

  .label-text {
    font-size: 0.875rem;
  }

  .readonly-note {
    font-size: 0.875rem;
  }

  select {
    background: var(--color-base-100);
    border: 1px solid var(--color-base-300);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    color: var(--color-base-content);
  }

  select:focus {
    outline: none;
    border-color: var(--color-primary);
  }
</style>
