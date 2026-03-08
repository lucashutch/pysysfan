import { describe, it, expect } from 'vitest'
import type { ServiceStatus } from './types'

describe('ServiceStatus type', () => {
  it('should have correct shape', () => {
    const status: ServiceStatus = {
      task_installed: true,
      task_enabled: true,
      task_status: 'Running',
      task_last_run: '2024-01-01T12:00:00',
      daemon_running: true,
      daemon_pid: 1234,
      daemon_healthy: true,
    }

    expect(status.task_installed).toBe(true)
    expect(status.daemon_running).toBe(true)
    expect(status.daemon_pid).toBe(1234)
  })

  it('should allow null values', () => {
    const status: ServiceStatus = {
      task_installed: false,
      task_enabled: false,
      task_status: null,
      task_last_run: null,
      daemon_running: false,
      daemon_pid: null,
      daemon_healthy: false,
    }

    expect(status.task_installed).toBe(false)
    expect(status.daemon_pid).toBeNull()
  })
})

describe('UI State logic', () => {
  function getUIState(s: ServiceStatus | null): string {
    if (!s) return 'unknown'
    if (!s.task_installed) return 'not_installed'
    if (!s.task_enabled) return 'disabled'
    if (!s.daemon_running) return 'stopped'
    if (s.daemon_running && s.daemon_healthy) return 'running'
    if (s.daemon_running && !s.daemon_healthy) return 'unhealthy'
    return 'unknown'
  }

  it('should return unknown for null status', () => {
    expect(getUIState(null)).toBe('unknown')
  })

  it('should return not_installed when task not installed', () => {
    const status: ServiceStatus = {
      task_installed: false,
      task_enabled: false,
      task_status: null,
      task_last_run: null,
      daemon_running: false,
      daemon_pid: null,
      daemon_healthy: false,
    }
    expect(getUIState(status)).toBe('not_installed')
  })

  it('should return disabled when task not enabled', () => {
    const status: ServiceStatus = {
      task_installed: true,
      task_enabled: false,
      task_status: 'Disabled',
      task_last_run: null,
      daemon_running: false,
      daemon_pid: null,
      daemon_healthy: false,
    }
    expect(getUIState(status)).toBe('disabled')
  })

  it('should return stopped when daemon not running', () => {
    const status: ServiceStatus = {
      task_installed: true,
      task_enabled: true,
      task_status: 'Ready',
      task_last_run: '2024-01-01T12:00:00',
      daemon_running: false,
      daemon_pid: null,
      daemon_healthy: false,
    }
    expect(getUIState(status)).toBe('stopped')
  })

  it('should return running when daemon healthy', () => {
    const status: ServiceStatus = {
      task_installed: true,
      task_enabled: true,
      task_status: 'Running',
      task_last_run: '2024-01-01T12:00:00',
      daemon_running: true,
      daemon_pid: 1234,
      daemon_healthy: true,
    }
    expect(getUIState(status)).toBe('running')
  })

  it('should return unhealthy when daemon running but not healthy', () => {
    const status: ServiceStatus = {
      task_installed: true,
      task_enabled: true,
      task_status: 'Running',
      task_last_run: '2024-01-01T12:00:00',
      daemon_running: true,
      daemon_pid: 1234,
      daemon_healthy: false,
    }
    expect(getUIState(status)).toBe('unhealthy')
  })
})
