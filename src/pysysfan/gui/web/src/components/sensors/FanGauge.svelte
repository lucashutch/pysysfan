<script lang="ts">
  interface Props {
    rpm: number
    maxRpm?: number
    controllable?: boolean
    label?: string
    controlValue?: number | null
  }

  let { rpm, maxRpm = 2000, controllable = true, label = 'Fan', controlValue = null }: Props = $props()

  const percentage = $derived(Math.min((rpm / maxRpm) * 100, 100))
</script>

<div class="flex flex-col items-center gap-2">
  <div class="radial-progress" class:text-primary={controllable} class:text-warning={!controllable} style="--value:{percentage}; --size:5rem;">
    <span class="text-lg font-bold">{rpm}</span>
  </div>
  <span class="text-sm font-medium opacity-80">{label}</span>
  <div class="flex flex-col items-center gap-1">
    <span class="text-xs opacity-60">RPM</span>
    {#if controllable}
      <span class="badge badge-success badge-sm">Controllable</span>
    {:else}
      <span class="badge badge-ghost badge-sm">Read-only</span>
    {/if}
    {#if controlValue !== null}
      <span class="text-xs opacity-70">{controlValue.toFixed(0)}%</span>
    {/if}
  </div>
</div>
