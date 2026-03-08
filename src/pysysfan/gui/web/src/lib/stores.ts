import { writable } from 'svelte/store'
import type { SystemState } from './types'

export const systemState = writable<SystemState | null>(null)
export const connectionStatus = writable<'connecting' | 'connected' | 'disconnected'>('connecting')
