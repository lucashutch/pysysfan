<script lang="ts">
  import { createEventDispatcher } from 'svelte'

  export let points: [number, number][] = []
  export let hysteresis: number = 3

  const dispatch = createEventDispatcher<{
    pointUpdate: { index: number; point: [number, number] }
    hysteresisUpdate: { value: number }
    addPoint: { point: [number, number] }
    removePoint: { index: number }
  }>()

  function handleTempChange(index: number, value: string) {
    const temp = parseInt(value, 10)
    if (isNaN(temp)) return
    const newPoints = [...points]
    newPoints[index] = [Math.max(20, Math.min(100, temp)), newPoints[index][1]]
    dispatch('pointUpdate', { index, point: newPoints[index] })
  }

  function handleSpeedChange(index: number, value: string) {
    const speed = parseInt(value, 10)
    if (isNaN(speed)) return
    const newPoints = [...points]
    newPoints[index] = [newPoints[index][0], Math.max(0, Math.min(100, speed))]
    dispatch('pointUpdate', { index, point: newPoints[index] })
  }

  function handleAddPoint() {
    const temps = points.map(p => p[0])
    const newTemp = temps.length > 0 ? Math.max(...temps) + 10 : 30
    dispatch('addPoint', { point: [Math.min(newTemp, 100), 50] })
  }

  function handleRemovePoint(index: number) {
    if (points.length <= 2) return
    dispatch('removePoint', { index })
  }

  function handleHysteresisChange(value: string) {
    const val = parseFloat(value)
    if (isNaN(val)) return
    dispatch('hysteresisUpdate', { value: Math.max(0, Math.min(20, val)) })
  }
</script>

<div class="curve-table">
  <div class="table-header">
    <h3 class="text-lg font-semibold">Curve Points</h3>
    <button class="btn btn-sm btn-primary" on:click={handleAddPoint}>
      + Add Point
    </button>
  </div>

  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Temperature (°C)</th>
          <th>Fan Speed (%)</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each points as point, i}
          <tr>
            <td class="index">{i + 1}</td>
            <td>
              <input
                type="number"
                min="20"
                max="100"
                value={point[0]}
                on:input={(e) => handleTempChange(i, e.currentTarget.value)}
                class="input input-bordered input-sm w-24"
              />
            </td>
            <td>
              <input
                type="number"
                min="0"
                max="100"
                value={point[1]}
                on:input={(e) => handleSpeedChange(i, e.currentTarget.value)}
                class="input input-bordered input-sm w-24"
              />
            </td>
            <td>
              {#if points.length > 2}
                <button
                  class="btn btn-ghost btn-xs text-error"
                  on:click={() => handleRemovePoint(i)}
                  title="Remove point"
                >
                  ✕
                </button>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <div class="hysteresis-row">
    <label class="label">
      <span class="label-text">Hysteresis (°C)</span>
    </label>
    <input
      type="number"
      min="0"
      max="20"
      step="0.5"
      value={hysteresis}
      on:input={(e) => handleHysteresisChange(e.currentTarget.value)}
      class="input input-bordered input-sm w-20"
    />
    <span class="text-sm opacity-60 ml-2">
      Prevents rapid fan speed changes
    </span>
  </div>
</div>

<style>
  .curve-table {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .table-container {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th {
    text-align: left;
    padding: 0.5rem;
    border-bottom: 2px solid var(--color-base-300);
    font-weight: 600;
  }

  td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--color-base-300);
  }

  .index {
    color: var(--color-base-content);
    opacity: 0.6;
    font-size: 0.875rem;
  }

  .hysteresis-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-top: 0.5rem;
  }

  .hysteresis-row .label {
    margin-bottom: 0;
  }

  input[type="number"] {
    background: var(--color-base-100);
    border: 1px solid var(--color-base-300);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    color: var(--color-base-content);
  }

  input[type="number"]:focus {
    outline: none;
    border-color: var(--color-primary);
  }
</style>
