export type UserRole =
  | 'STUDENT'
  | 'STAFF'
  | 'TECHNICIAN'
  | 'SUPERVISOR'
  | 'FACILITY_MANAGER'
  | 'IT_MANAGER'
  | 'DEPARTMENT_HEAD'
  | 'CAMPUS_ADMIN'
  | 'SYSTEM_ADMIN'

export interface AuthUser {
  id: number
  email: string
  full_name: string
  phone_number: string
  role: UserRole
  date_joined: string
  team_ids: number[]
}

export type IssueStatus = 'OPEN' | 'IN_REVIEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED' | 'REOPENED'
export type IssuePriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface IssueCategory {
  id: number
  name: string
  description: string
  icon_identifier: string
  is_active: boolean
}

export interface LocationOption {
  id: number
  name: string
  building_name: string | null
  display_name: string
  kind: string
  is_active: boolean
}

export interface AssetOption {
  id: number
  asset_code: string
  name: string
  asset_type: string
  location: number
  location_name: string
  qr_identifier: string
  qr_endpoint: string
  is_active: boolean
}

export interface IssueAttachment {
  id: number
  file_url: string
  content_type: string
  uploaded_by: number
  uploaded_by_name: string
  created_at: string
}

export interface IssueEvent {
  id: number
  from_status: IssueStatus | ''
  to_status: IssueStatus
  note: string
  actor_name: string | null
  created_at: string
}

export interface IssueRecord {
  id: number
  ticket_number: string
  title: string
  description?: string
  category: IssueCategory
  location: number
  location_name: string
  asset: number | null
  asset_name: string | null
  reporter: number
  reporter_name: string | null
  reporter_email?: string | null
  assigned_to: number | null
  assigned_to_name: string | null
  assigned_team: number | null
  assigned_team_name: string | null
  priority: IssuePriority
  status: IssueStatus
  created_at: string
  updated_at: string
  resolved_at: string | null
  closed_at: string | null
  sla_state?: 'ON_TRACK' | 'AT_RISK' | 'BREACHED' | 'COMPLETED' | 'NOT_CONFIGURED' | null
  response_sla_state?: string | null
  resolution_sla_state?: string | null
  response_due_at?: string | null
  resolution_due_at?: string | null
  sla_policy_name?: string | null
  response_breached_at?: string | null
  resolution_breached_at?: string | null
  current_escalation_level?: number | null
  assignment_history?: { team: string | null; user: string | null; reason: string; automatic: boolean; rule: string | null; created_at: string }[]
  attachments?: IssueAttachment[]
  events?: IssueEvent[]
}

export interface IssueNetworkContext {
  id: number
  issue: number
  measurement_id: number
  created_by: number
  created_at: string
  evaluator_version: string
  overall_quality: NetworkQualityLevel
  primary_factor: string
  measured_at: string
  network_name: string
  network_kind: NetworkKind
  device_name: string | null
  device_code: string | null
  location_name: string
  latency_ms: string | null
  packet_loss_percent: string | null
  download_mbps: string | null
  upload_mbps: string | null
  signal_strength_dbm: number | null
  connection_state: NetworkConnectionState
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type WorkOrderStatus = 'ASSIGNED' | 'ACCEPTED' | 'IN_PROGRESS' | 'COMPLETED' | 'VERIFIED' | 'REWORK' | 'CANCELLED' | 'CLOSED'

export interface WorkOrderEvent {
  id: number
  event_type: string
  from_status: WorkOrderStatus | ''
  to_status: WorkOrderStatus | ''
  note: string
  actor_name: string | null
  created_at: string
}

export interface WorkOrderEvidence {
  id: number
  file_url: string
  content_type: string
  caption: string
  uploaded_by: number
  uploaded_by_name: string
  created_at: string
}

export interface WorkOrderRecord {
  id: number
  number: string
  issue: number
  issue_ticket_number: string
  issue_title: string
  team: number
  team_name: string
  assigned_to: number | null
  assigned_to_name: string | null
  title: string
  priority: IssuePriority
  status: WorkOrderStatus
  created_at: string
  accepted_at: string | null
  started_at: string | null
  completed_at: string | null
  verified_at: string | null
  closed_at: string | null
}

export interface WorkOrderDetail extends WorkOrderRecord {
  instructions: string
  created_by: number | null
  created_by_name: string | null
  completed_by: number | null
  completed_by_name: string | null
  verified_by: number | null
  verified_by_name: string | null
  resolution_summary: string
  cancellation_reason: string
  rework_reason: string
  issue_sla_deadline: string | null
  updated_at: string
  assignments: { id: number; team: number; team_name: string; technician: number | null; technician_name: string | null; assigned_by_name: string | null; reason: string; created_at: string }[]
  events: WorkOrderEvent[]
  notes: { id: number; author: number; author_name: string; body: string; created_at: string }[]
  materials: { id: number; name: string; quantity: string; note: string; recorded_by_name: string; created_at: string }[]
  evidence: WorkOrderEvidence[]
}

export interface NotificationRecord {
  id: number
  notification_type: string
  title: string
  message: string
  issue: number | null
  read_at: string | null
  created_at: string
}

export type NetworkKind = 'WIFI' | 'LAN' | 'WAN'
export type NetworkDeviceKind = 'ACCESS_POINT' | 'SWITCH' | 'ROUTER' | 'GATEWAY'
export type NetworkDeviceState = 'DEPLOYED' | 'MAINTENANCE' | 'RETIRED'
export type NetworkConnectionState = 'CONNECTED' | 'DEGRADED' | 'DISCONNECTED' | 'UNKNOWN'

export interface NetworkRecord {
  id: number
  campus: number
  campus_name: string
  building: number | null
  building_name: string | null
  code: string
  name: string
  kind: NetworkKind
  description: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface NetworkDeviceRecord {
  id: number
  device_code: string
  name: string
  kind: NetworkDeviceKind
  network: number
  network_name: string
  network_code: string
  campus_name: string
  location: number
  location_name: string
  asset: number | null
  asset_code: string | null
  manufacturer: string
  model_number: string
  serial_number: string
  state: NetworkDeviceState
  created_at: string
  updated_at: string
}

export interface NetworkMeasurementRecord {
  id: number
  network: number
  network_name: string
  location: number
  location_name: string
  device: number | null
  device_code: string | null
  recorded_by: number
  recorded_by_name: string
  measured_at: string
  latency_ms: string | null
  packet_loss_percent: string | null
  download_mbps: string | null
  upload_mbps: string | null
  signal_strength_dbm: number | null
  connection_state: NetworkConnectionState
  note: string
  quality_evaluation: NetworkQualityEvaluation
}

export interface NetworkQualityMetric {
  key: string
  label: string
  value: string | null
  unit: string | null
  quality: string | null
  status: string
  reason: string
}

export interface NetworkQualityEvaluation {
  measurement: { id: number; network: number; network_name: string; network_kind: NetworkKind; device: number | null; device_code: string | null; device_name: string | null; location: number; location_name: string; measured_at: string }
  overall_quality: 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' | 'CRITICAL' | 'INSUFFICIENT_DATA'
  overall_label: string
  metrics: NetworkQualityMetric[]
  primary_factor: string | null
  primary_factor_label: string | null
  reasons: string[]
  evaluation_version: string
}

export type NetworkQualityLevel = NetworkQualityEvaluation['overall_quality'] | 'POOR' | 'CRITICAL'
export interface AnalyticsWindow { start: string; end: string; range: string; timezone: string }
export interface AnalyticsQualityBucket { count: number; percentage: number }
export interface AnalyticsLatestMeasurement {
  id: number; network: number; network_name: string; device: number | null; device_code: string | null
  location: number; location_name: string; measured_at: string; overall_quality?: NetworkQualityLevel
  quality: NetworkQualityLevel; device_name: string | null; device_type: NetworkDeviceKind | null
  network_type: NetworkKind; evaluation_version: string
}
export interface NetworkAnalyticsSummary {
  window: AnalyticsWindow; total_measurements: number; overall_quality: NetworkQualityLevel
  quality_distribution: Record<NetworkQualityLevel, AnalyticsQualityBucket>
  poor_count: number; critical_count: number; insufficient_data_count: number
  degraded_measurement_count: number; latest_measurement: AnalyticsLatestMeasurement | null
  primary_factors: AnalyticsFactor[]; evaluation_version: string
}
export interface AnalyticsGroup {
  id: number; measurement_count: number; overall_quality: NetworkQualityLevel
  quality_distribution: Record<NetworkQualityLevel, AnalyticsQualityBucket>
  poor_count: number; critical_count: number; latest_measurement: AnalyticsLatestMeasurement
  campus_name?: string; building_name?: string | null; location_name?: string
  device_code?: string; device_name?: string; device_type?: NetworkDeviceKind
  location_id?: number; network_id?: number; network_name?: string; network_type?: NetworkKind
}
export interface AnalyticsFactor { factor: string; count: number; percentage_of_degraded_measurements: number }
export type AnalyticsPage<T> = Paginated<T> & { window: AnalyticsWindow }

export type NetworkTrendQuality = 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' | 'CRITICAL' | 'INSUFFICIENT_DATA'
export type NetworkTrendComparisonStatus = 'IMPROVED' | 'WORSENED' | 'STABLE' | 'NO_COMPARISON' | 'NO_DATA'
export interface NetworkTrendFactor { factor: string; count: number }
export interface NetworkTrendBucket {
  bucket: string
  total_measurements: number
  excellent: number
  good: number
  fair: number
  poor: number
  critical: number
  insufficient_data: number
  degraded: number
  degraded_percentage: number
  poor_or_critical: number
  excellent_percentage: number
  good_percentage: number
  fair_percentage: number
  poor_percentage: number
  critical_percentage: number
  insufficient_data_percentage: number
  latest_measurement_at: string
  overall_quality: NetworkTrendQuality
  primary_factors: NetworkTrendFactor[]
}
export interface NetworkTrendComparison {
  status: NetworkTrendComparisonStatus
  first_degraded_percentage: number | null
  latest_degraded_percentage: number | null
  change_percentage_points: number | null
}
export interface NetworkTrendResponse {
  window: AnalyticsWindow
  bucket_size: 'hour' | 'day'
  buckets: NetworkTrendBucket[]
  comparison: NetworkTrendComparison
  factor_trend: { bucket: string; factors: NetworkTrendFactor[] }[]
}
