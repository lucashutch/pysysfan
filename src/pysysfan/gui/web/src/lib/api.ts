import type { SystemState, AuthResponse, DaemonStatus, SensorData, ServiceStatus } from './types'

const API_BASE = 'http://localhost:8765/api'

type SensorCallback = (data: SensorData) => void

export class PySysFanAPI {
  private baseUrl: string
  private token: string | null = null
  private eventSource: EventSource | null = null

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  setToken(token: string) {
    this.token = token
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    })

    if (response.status === 401) {
      throw new Error('Authentication failed')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `API error: ${response.statusText}`)
    }

    return response.json()
  }

  async initialize(): Promise<void> {
    this.token = localStorage.getItem('pysysfan_token')
  }

  async login(password: string): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
    this.token = response.access_token
    localStorage.setItem('pysysfan_token', response.access_token)
    return response
  }

  async getState(): Promise<DaemonStatus> {
    return this.request<DaemonStatus>('/status')
  }

  async getSensors(): Promise<SensorData> {
    return this.request<SensorData>('/sensors')
  }

  subscribeToSensors(callback: SensorCallback): () => void {
    if (this.eventSource) {
      this.eventSource.close()
    }

    const tokenParam = this.token ? `?token=${encodeURIComponent(this.token)}` : ''
    const url = `${this.baseUrl}/stream${tokenParam}`
    this.eventSource = new EventSource(url)

    this.eventSource.addEventListener('sensors', (event) => {
      const data = JSON.parse(event.data) as SensorData
      callback(data)
    })

    this.eventSource.addEventListener('error', (event) => {
      console.error('SSE Error:', event)
    })

    return () => {
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
    }
  }

  async setFanSpeed(fanId: string, speed: number): Promise<void> {
    await this.request(`/fans/${fanId}/speed`, {
      method: 'POST',
      body: JSON.stringify({ speed }),
    })
  }

  async updateCurve(curveId: string, points: [number, number][], hysteresis?: number): Promise<void> {
    const body: Record<string, unknown> = { points }
    if (hysteresis !== undefined) {
      body.hysteresis = hysteresis
    }
    await this.request(`/curves/${curveId}`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async validateCurve(points: [number, number][], hysteresis?: number): Promise<{ valid: boolean; errors: string[] }> {
    const body: Record<string, unknown> = { points }
    if (hysteresis !== undefined) {
      body.hysteresis = hysteresis
    }
    return this.request('/curves/validate', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async getCurves(): Promise<Record<string, { name: string; points: [number, number][]; hysteresis: number }>> {
    const response = await this.request<{ curves: Record<string, { name: string; points: [number, number][]; hysteresis: number }> }>('/curves')
    return response.curves
  }

  async getServiceStatus(): Promise<ServiceStatus> {
    return this.request<ServiceStatus>('/service/status')
  }

  async installService(configPath?: string): Promise<{ success: boolean; message: string }> {
    const url = configPath ? `/service/install?config_path=${encodeURIComponent(configPath)}` : '/service/install'
    return this.request(url, { method: 'POST' })
  }

  async uninstallService(): Promise<{ success: boolean; message: string }> {
    return this.request('/service/uninstall', { method: 'POST' })
  }

  async enableService(): Promise<{ success: boolean; message: string }> {
    return this.request('/service/enable', { method: 'POST' })
  }

  async disableService(): Promise<{ success: boolean; message: string }> {
    return this.request('/service/disable', { method: 'POST' })
  }

  async startService(): Promise<{ success: boolean; message: string }> {
    return this.request('/service/start', { method: 'POST' })
  }

  async stopService(): Promise<{ success: boolean; message: string; method?: string }> {
    return this.request('/service/stop', { method: 'POST' })
  }

  async restartService(): Promise<{ success: boolean; message: string }> {
    return this.request('/service/restart', { method: 'POST' })
  }

  async getServiceLogs(lines: number = 100): Promise<{ logs: string[]; total_lines: number }> {
    return this.request(`/service/logs?lines=${lines}`)
  }
}

export const api = new PySysFanAPI()
