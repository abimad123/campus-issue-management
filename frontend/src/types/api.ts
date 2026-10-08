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

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
