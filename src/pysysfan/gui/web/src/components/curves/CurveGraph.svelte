<script lang="ts">
  import { createEventDispatcher } from 'svelte'

  export let points: [number, number][] = []
  export let width = 500
  export let height = 300

  const dispatch = createEventDispatcher<{
    pointMove: { index: number; point: [number, number] }
  }>()

  const padding = { top: 20, right: 20, bottom: 40, left: 50 }
  const tempMin = 20
  const tempMax = 100
  const speedMin = 0
  const speedMax = 100

  $: graphWidth = width - padding.left - padding.right
  $: graphHeight = height - padding.top - padding.bottom

  function tempToX(temp: number): number {
    return padding.left + ((temp - tempMin) / (tempMax - tempMin)) * graphWidth
  }

  function speedToY(speed: number): number {
    return padding.top + graphHeight - ((speed - speedMin) / (speedMax - speedMin)) * graphHeight
  }

  function xToTemp(x: number): number {
    return tempMin + ((x - padding.left) / graphWidth) * (tempMax - tempMin)
  }

  function yToSpeed(y: number): number {
    return speedMin + ((padding.top + graphHeight - y) / graphHeight) * (speedMax - speedMin)
  }

  function getPath(): string {
    if (points.length < 2) return ''
    const sorted = [...points].sort((a, b) => a[0] - b[0])
    let path = `M ${tempToX(sorted[0][0])} ${speedToY(sorted[0][1])}`
    for (let i = 1; i < sorted.length; i++) {
      path += ` L ${tempToX(sorted[i][0])} ${speedToY(sorted[i][1])}`
    }
    return path
  }

  let draggingIndex: number | null = null

  function handleMouseDown(index: number) {
    draggingIndex = index
  }

  function handleMouseMove(event: MouseEvent) {
    if (draggingIndex === null) return
    const svg = event.currentTarget as SVGSVGElement
    const rect = svg.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    const temp = Math.round(Math.max(tempMin, Math.min(tempMax, xToTemp(x))))
    const speed = Math.round(Math.max(speedMin, Math.min(speedMax, yToSpeed(y))))

    dispatch('pointMove', { index: draggingIndex, point: [temp, speed] })
  }

  function handleMouseUp() {
    draggingIndex = null
  }

  function handleGridLines(): { x: number; label: string }[] {
    const lines = []
    for (let t = 20; t <= 100; t += 20) {
      lines.push({ x: tempToX(t), label: `${t}°C` })
    }
    return lines
  }

  function handleYGridLines(): { y: number; label: string }[] {
    const lines = []
    for (let s = 0; s <= 100; s += 25) {
      lines.push({ y: speedToY(s), label: `${s}%` })
    }
    return lines
  }
</script>

<svg
  {width}
  {height}
  class="curve-graph"
  on:mousemove={handleMouseMove}
  on:mouseup={handleMouseUp}
  on:mouseleave={handleMouseUp}
  role="img"
  aria-label="Fan curve graph"
>
  <defs>
    <clipPath id="graph-area">
      <rect x={padding.left} y={padding.top} width={graphWidth} height={graphHeight} />
    </clipPath>
  </defs>

  {#each handleGridLines() as line}
    <line
      x1={line.x}
      y1={padding.top}
      x2={line.x}
      y2={padding.top + graphHeight}
      stroke="var(--color-base-300)"
      stroke-width="1"
      stroke-dasharray="4"
    />
    <text x={line.x} y={height - 10} text-anchor="middle" class="axis-label">
      {line.label}
    </text>
  {/each}

  {#each handleYGridLines() as line}
    <line
      x1={padding.left}
      y1={line.y}
      x2={padding.left + graphWidth}
      y2={line.y}
      stroke="var(--color-base-300)"
      stroke-width="1"
      stroke-dasharray="4"
    />
    <text x={padding.left - 10} y={line.y + 4} text-anchor="end" class="axis-label">
      {line.label}
    </text>
  {/each}

  <rect
    x={padding.left}
    y={padding.top}
    width={graphWidth}
    height={graphHeight}
    fill="transparent"
    stroke="var(--color-base-content)"
    stroke-width="1"
  />

  <path
    d={getPath()}
    fill="none"
    stroke="var(--color-primary)"
    stroke-width="3"
    stroke-linecap="round"
    stroke-linejoin="round"
    clip-path="url(#graph-area)"
  />

  {#each points as point, i}
    <circle
      cx={tempToX(point[0])}
      cy={speedToY(point[1])}
      r="8"
      class="point"
      class:dragging={draggingIndex === i}
      on:mousedown|stopPropagation={() => handleMouseDown(i)}
      role="button"
      tabindex="0"
      aria-label="Drag point {i + 1}"
    />
    <text
      x={tempToX(point[0])}
      y={speedToY(point[1]) - 15}
      text-anchor="middle"
      class="point-label"
    >
      {point[1]}%
    </text>
  {/each}
</svg>

<style>
  .curve-graph {
    display: block;
    background: var(--color-base-200);
    border-radius: 8px;
  }

  .axis-label {
    font-size: 11px;
    fill: var(--color-base-content);
    opacity: 0.7;
  }

  .point {
    fill: var(--color-primary);
    stroke: var(--color-base-100);
    stroke-width: 2;
    cursor: grab;
    transition: r 0.15s ease;
  }

  .point:hover {
    r: 10;
  }

  .point.dragging {
    cursor: grabbing;
    fill: var(--color-accent);
  }

  .point-label {
    font-size: 10px;
    fill: var(--color-base-content);
    pointer-events: none;
  }
</style>
