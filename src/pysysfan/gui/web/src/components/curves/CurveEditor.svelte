<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api'
  import { debounce } from '../lib/debounce'
  import CurveGraph from './CurveGraph.svelte'
  import CurveTable from './CurveTable.svelte'

  export let curveName: string = 'balanced'

  type SaveState = 'idle' | 'editing' | 'saving' | 'saved' | 'error'

  let points: [number, number][] = []
  let hysteresis = 3
  let saveState: SaveState = 'idle'
  let errors: string[] = []
  let loading = true

  const debouncedSave = debounce(async () => {
    saveState = 'saving'
    try {
      const validation = await api.validateCurve(points, hysteresis)
      if (!validation.valid) {
        errors = validation.errors
        saveState = 'error'
        return
      }
      errors = []
      await api.updateCurve(curveName, points, hysteresis)
      saveState = 'saved'
      setTimeout(() => {
        if (saveState === 'saved') {
          saveState = 'idle'
        }
      }, 2000)
    } catch (e) {
      console.error('Failed to save curve:', e)
      saveState = 'error'
    }
  }, 500)

  function handleCurveChange() {
    saveState = 'editing'
    errors = []
    debouncedSave()
  }

  function handlePointMove(event: CustomEvent<{ index: number; point: [number, number] }>) {
    const { index, point } = event.detail
    points[index] = point
    points = [...points].sort((a, b) => a[0] - b[0])
    handleCurveChange()
  }

  function handlePointUpdate(event: CustomEvent<{ index: number; point: [number, number] }>) {
    const { index, point } = event.detail
    points[index] = point
    points = [...points].sort((a, b) => a[0] - b[0])
    handleCurveChange()
  }

  function handleHysteresisUpdate(event: CustomEvent<{ value: number }>) {
    hysteresis = event.detail.value
    handleCurveChange()
  }

  function handleAddPoint(event: CustomEvent<{ point: [number, number] }>) {
    points = [...points, event.detail.point]
    points = [...points].sort((a, b) => a[0] - b[0])
    handleCurveChange()
  }

  function handleRemovePoint(event: CustomEvent<{ index: number }>) {
    points = points.filter((_, i) => i !== event.detail.index)
    handleCurveChange()
  }

  onMount(async () => {
    try {
      const curves = await api.getCurves()
      const curve = curves[curveName]
      if (curve) {
        points = curve.points as [number, number][]
        hysteresis = curve.hysteresis
      } else {
        points = [[30, 30], [60, 60], [75, 85], [85, 100]]
      }
    } catch (e) {
      console.error('Failed to load curve:', e)
      points = [[30, 30], [60, 60], [75, 85], [85, 100]]
    } finally {
      loading = false
    }
  })
</script>

<div class="curve-editor">
  <div class="editor-header">
    <h2 class="text-xl font-bold">Edit Curve: {curveName}</h2>
    <div class="save-indicator">
      {#if saveState === 'editing'}
        <span class="text-sm opacity-50">Editing...</span>
      {:else if saveState === 'saving'}
        <span class="text-sm text-info">Saving...</span>
      {:else if saveState === 'saved'}
        <span class="text-sm text-success">✓ Saved</span>
      {:else if saveState === 'error'}
        <span class="text-sm text-error">Save failed</span>
        <button class="btn btn-ghost btn-xs" on:click={debouncedSave}>Retry</button>
      {/if}
    </div>
  </div>

  {#if errors.length > 0}
    <div class="alert alert-warning mb-4">
      <ul class="list-disc list-inside">
        {#each errors as error}
          <li>{error}</li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if loading}
    <div class="flex justify-center p-8">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>
  {:else}
    <div class="editor-content">
      <div class="graph-container">
        <CurveGraph {points} on:pointMove={handlePointMove} />
      </div>
      <div class="table-container">
        <CurveTable
          {points}
          {hysteresis}
          on:pointUpdate={handlePointUpdate}
          on:hysteresisUpdate={handleHysteresisUpdate}
          on:addPoint={handleAddPoint}
          on:removePoint={handleRemovePoint}
        />
      </div>
    </div>
  {/if}
</div>

<style>
  .curve-editor {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
  }

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .save-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .editor-content {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
  }

  @media (min-width: 1024px) {
    .editor-content {
      grid-template-columns: 1fr 1fr;
    }
  }

  .graph-container {
    display: flex;
    justify-content: center;
  }

  .text-info {
    color: var(--color-info);
  }

  .text-success {
    color: var(--color-success);
  }

  .text-error {
    color: var(--color-error);
  }
</style>
