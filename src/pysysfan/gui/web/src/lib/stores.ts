import { writable } from 'svelte/store'
import type { DaemonStatus, SensorData } from './types'

export const daemonStatus = writable<DaemonStatus | null>(null)
export const sensorData = writable<SensorData | null>(null)
export const sensorHistory = writable<{
  temperatures: Record<string, { time: number; value: number }[]>
  fans: Record<string, { time: number; value: number }[]>
}>({
  temperatures: {},
  fans: {},
})
export const connectionStatus = writable<'connecting' | 'connected' | 'disconnected'>('connecting')
