<script lang="ts">
  interface Props {
    value: number
    min?: number
    max?: number
    label?: string
  }

  let { value, min = 0, max = 100, label = 'Temperature' }: Props = $props()

  const percentage = $derived(((value - min) / (max - min)) * 100)
  
  const color = $derived.by(() => {
    if (value < 50) return 'success'
    if (value < 70) return 'warning'
    return 'error'
  })
</script>

<div class="flex flex-col items-center gap-2">
  <div class="radial-progress text-primary" style="--value:{percentage}; --size:5rem;">
    <span class="text-lg font-bold">{value.toFixed(1)}°C</span>
  </div>
  <span class="text-sm font-medium opacity-80">{label}</span>
  <div class="badge badge-{color} badge-sm">{color.toUpperCase()}</div>
</div>
