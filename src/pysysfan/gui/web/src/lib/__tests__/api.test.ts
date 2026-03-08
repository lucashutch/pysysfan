import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
global.fetch = mockFetch

const API_BASE = 'http://localhost:8765/api'

describe('PySysFanAPI - Service methods', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should get service status', async () => {
    const mockStatus = {
      task_installed: true,
      task_enabled: true,
      task_status: 'Running',
      task_last_run: '2024-01-01T12:00:00',
      daemon_running: true,
      daemon_pid: 1234,
      daemon_healthy: true,
    }

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStatus),
    })

    const { api } = await import('../api')
    const status = await api.getServiceStatus()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/status`,
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) })
    )
    expect(status).toEqual(mockStatus)
  })

  it('should install service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Service installed' }),
    })

    const { api } = await import('../api')
    const result = await api.installService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/install`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should install service with config path', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Service installed' }),
    })

    const { api } = await import('../api')
    const result = await api.installService('/path/to/config.yaml')

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/install?config_path=%2Fpath%2Fto%2Fconfig.yaml`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should uninstall service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Service uninstalled' }),
    })

    const { api } = await import('../api')
    const result = await api.uninstallService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/uninstall`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should enable service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Service enabled' }),
    })

    const { api } = await import('../api')
    const result = await api.enableService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/enable`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should disable service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Service disabled' }),
    })

    const { api } = await import('../api')
    const result = await api.disableService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/disable`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should start service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Daemon started' }),
    })

    const { api } = await import('../api')
    const result = await api.startService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/start`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should stop service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Daemon stopped via graceful_api', method: 'graceful_api' }),
    })

    const { api } = await import('../api')
    const result = await api.stopService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/stop`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
    expect(result.method).toBe('graceful_api')
  })

  it('should restart service', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'Daemon restarted' }),
    })

    const { api } = await import('../api')
    const result = await api.restartService()

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/restart`,
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })

  it('should get service logs', async () => {
    const mockLogs = {
      logs: ['line 1', 'line 2', 'line 3'],
      total_lines: 3,
    }

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockLogs),
    })

    const { api } = await import('../api')
    const result = await api.getServiceLogs(100)

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/service/logs?lines=100`,
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) })
    )
    expect(result.logs).toEqual(['line 1', 'line 2', 'line 3'])
  })
})
