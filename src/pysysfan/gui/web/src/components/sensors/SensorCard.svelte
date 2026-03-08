<script lang="ts">
  import type { Snippet } from 'svelte'

  interface Props {
    title: string
    icon?: string
    children: Snippet
  }

  let { title, icon = '', children }: Props = $props()
</script>

<div class="card bg-base-200 shadow-xl">
  <div class="card-body">
    <div class="flex items-center gap-2">
      {#if icon}
        <span class="text-lg">{icon}</span>
      {/if}
      <h3 class="card-title text-base">{title}</h3>
    </div>
    {@render children()}
  </div>
</div>
