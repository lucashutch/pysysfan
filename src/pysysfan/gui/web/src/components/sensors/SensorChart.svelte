<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { Chart, registerables } from 'chart.js'

  Chart.register(...registerables)

  interface Props {
    data: { time: number; value: number }[]
    label: string
    color?: string
    unit?: string
    min?: number
    max?: number
  }

  let { data = [], label, color = '#3b82f6', unit = '', min, max }: Props = $props()

  let canvas: HTMLCanvasElement
  let chart: Chart | null = null

  const chartData = $derived({
    labels: data.map(d => new Date(d.time * 1000).toLocaleTimeString()),
    datasets: [{
      label,
      data: data.map(d => d.value),
      borderColor: color,
      backgroundColor: color + '20',
      fill: true,
      tension: 0.4,
    }]
  })

  const chartOptions = $derived({
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    scales: {
      y: {
        min,
        max,
        title: { display: true, text: unit }
      },
      x: {
        display: false
      }
    },
    plugins: {
      legend: { display: false }
    }
  })

  onMount(() => {
    if (canvas) {
      chart = new Chart(canvas, {
        type: 'line',
        data: chartData,
        options: chartOptions
      })
    }
  })

  $effect(() => {
    if (chart) {
      chart.data = chartData
      chart.update('none')
    }
  })

  onDestroy(() => {
    if (chart) {
      chart.destroy()
    }
  })
</script>

<div class="h-32 w-full">
  <canvas bind:this={canvas}></canvas>
</div>
