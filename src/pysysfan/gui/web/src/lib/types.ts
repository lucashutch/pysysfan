export interface TemperatureSensor {
  id: string
  name: string
  value: number
  min: number
  max: number
}

export interface FanConfig {
  id: string
  name: string
  curve_id: string
  sensor_ids: string[]
  min_speed: number
  max_speed: number
}

export interface Curve {
  id: string
  name: string
  points: [number, number][]
  hysteresis: number
}

export interface SystemState {
  temperatures: TemperatureSensor[]
  fans: FanConfig[]
  curves: Curve[]
  is_running: boolean
}

export interface APIError {
  detail: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
}
