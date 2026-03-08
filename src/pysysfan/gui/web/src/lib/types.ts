export interface TemperatureSensor {
  identifier: string
  hardware_name: string
  sensor_name: string
  value: number
}

export interface FanSensor {
  identifier: string
  hardware_name: string
  sensor_name: string
  rpm: number
  control_percentage?: number
  controllable?: boolean
}

export interface ControlSensor {
  identifier: string
  hardware_name: string
  sensor_name: string
  current_value: number
  has_control: boolean
}

export interface SensorData {
  temperatures: TemperatureSensor[]
  fans: FanSensor[]
  controls: ControlSensor[]
  timestamp: number
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

export interface DaemonStatus {
  pid: number | null
  config_path: string
  started_at: number | null
  running: boolean
  uptime_seconds: number
  last_poll_time: number | null
  last_error: string | null
  poll_interval: number
  fans_configured: number
  curves_configured: number
  active_profile: string
  current_temps: Record<string, number>
  current_fan_speeds: Record<string, number>
  current_targets: Record<string, number>
  auto_reload_enabled: boolean
  api_enabled: boolean
  api_port: number
}

export interface APIError {
  detail: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
}
