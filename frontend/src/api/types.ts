/**
 * [INPUT]: 无外部依赖，纯类型定义
 * [OUTPUT]: 对外提供 HealthResponse, SystemStatus, PipelineRun, AgentState 类型
 * [POS]: api 模块的类型契约层，被 client 调用方和页面组件消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

// ----------------------------------------------------------------
// Health check
// ----------------------------------------------------------------

export type HealthResponse = {
  status: string
}

// ----------------------------------------------------------------
// System status
// ----------------------------------------------------------------

export type SystemStatus = {
  backend_status: string
  worker_status: string
  feishu_status: string
  opencli_status: string
  active_pipeline_runs: number
  pending_steps: number
  failed_steps: number
}

// ----------------------------------------------------------------
// Pipeline run
// ----------------------------------------------------------------

export type PipelineRun = {
  id: string
  name: string
  status:
    | "pending"
    | "running"
    | "waiting_approval"
    | "paused"
    | "failed"
    | "completed"
  created_at: string
  updated_at: string
}

// ----------------------------------------------------------------
// Agent state
// ----------------------------------------------------------------

export type AgentState = {
  id: string
  agent_type: string
  status: string
  book_id: string | null
  last_run_at: string | null
}
