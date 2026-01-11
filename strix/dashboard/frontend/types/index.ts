export interface DashboardState {
  scan_config: Record<string, any>
  agents: Record<string, Agent>
  tool_executions: ToolExecution[]
  chat_messages: ChatMessage[]
  vulnerabilities: Vulnerability[]
  collaboration: Collaboration
  resources: Resources
  rate_limiter: RateLimiter
  time: TimeInfo
  current_step: CurrentStep
  live_feed: LiveFeedEntry[]
  last_updated: string | null
  server_metrics?: ServerMetrics
}

export interface ServerMetrics {
  uptime_seconds: number
  request_rate_per_minute: number
  error_rate: number
  total_requests: number
  tool_count: number
  connection_pool: {
    pool_size: number
    active_connections: number
  }
  circuit_breaker: {
    state: 'closed' | 'open' | 'half_open'
  }
}

export interface Agent {
  id: string
  name: string
  status: 'running' | 'waiting' | 'completed' | 'failed' | 'stopped'
  task: string
  parent_id?: string
  created_at?: string
  updated_at?: string
  tool_executions?: number
  iteration?: number
  max_iterations?: number
}

export interface ToolExecution {
  execution_id: number
  agent_id: string
  tool_name: string
  args: Record<string, any>
  status: 'running' | 'completed' | 'failed'
  result?: any
  timestamp: string
  started_at: string
  completed_at?: string
}

export interface ChatMessage {
  message_id: number
  content: string
  role: 'user' | 'assistant' | 'system'
  agent_id?: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface Vulnerability {
  id: string
  title: string
  content: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  timestamp: string
  target?: string
  vulnerability_type?: string
}

export interface Collaboration {
  claims: Claim[]
  findings: Finding[]
  work_queue: WorkQueueItem[]
  help_requests: HelpRequest[]
  messages: CollaborationMessage[]
  stats: CollaborationStats
}

export interface Claim {
  agent_id: string
  agent_name: string
  target: string
  test_type: string
  priority?: string
  claimed_at: string
}

export interface Finding {
  finding_id: string
  title: string
  vulnerability_type: string
  severity: string
  target?: string
  found_by?: string
  chainable?: boolean
}

export interface WorkQueueItem {
  work_id: string
  target: string
  description?: string
  priority?: string
  test_types?: string[]
}

export interface HelpRequest {
  request_id: string
  help_type: string
  description: string
  urgency?: string
  requested_by?: string
}

export interface CollaborationMessage {
  message_id: string
  content: string
  sender: string
  timestamp: string
}

export interface CollaborationStats {
  total_claims?: number
  total_findings?: number
  total_work_items?: number
  total_help_requests?: number
  duplicate_tests_prevented?: number
  chaining_opportunities?: number
}

export interface Resources {
  input_tokens: number
  output_tokens: number
  cached_tokens: number
  total_cost: number
  request_count: number
  api_calls: number
}

export interface RateLimiter {
  current_rate: number
  max_rate: number
  remaining_capacity: number
  total_requests: number
  total_wait_time: number
}

export interface TimeInfo {
  start_time: string | null
  duration_minutes: number
  warning_minutes: number
  elapsed_minutes: number
  remaining_minutes: number
  progress_percentage: number
  status: string
  is_warning: boolean
  is_critical: boolean
}

export interface CurrentStep {
  agent_id: string | null
  agent_name: string | null
  action: string | null
  tool_name: string | null
  status: string
  details: Record<string, any>
  updated_at?: string
}

export interface LiveFeedEntry {
  type: 'thinking' | 'tool_execution' | 'tool_result' | 'error' | 'vulnerability' | 'agent_created' | 'chat_message'
  timestamp: string
  content?: string
  tool_name?: string
  args_summary?: string
  status?: string
  agent_id?: string
  agent_name?: string
  severity?: string
  title?: string
  role?: string
  content_preview?: string
  message?: string
}

export interface HistoricalData {
  timestamp: string
  tokens?: {
    input: number
    output: number
    cached: number
  }
  cost?: number
  rate?: number
  tool_executions?: number
  agent_count?: number
}