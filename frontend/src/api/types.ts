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
  status: string;
};

// ----------------------------------------------------------------
// System status
// ----------------------------------------------------------------

export type SystemStatus = {
  backend_status: string;
  worker_status: string;
  feishu_status: string;
  opencli_status: string;
  active_pipeline_runs: number;
  pending_steps: number;
  failed_steps: number;
};

// ----------------------------------------------------------------
// Pipeline run
// ----------------------------------------------------------------

export type PipelineRun = {
  id: string;
  name: string;
  status:
    | "pending"
    | "running"
    | "waiting_approval"
    | "paused"
    | "failed"
    | "completed";
  created_at: string;
  updated_at: string;
};

// ----------------------------------------------------------------
// Agent state
// ----------------------------------------------------------------

export type AgentState = {
  id: string;
  agent_type: string;
  status: string;
  book_id: string | null;
  last_run_at: string | null;
};

export type Hotspot = {
  hotspot_id: string;
  source: "douyin" | "manual";
  title: string;
  url: string;
  rank: number;
  heat_value: number;
  category: string;
  captured_at: string;
  status: string;
  dedupe_hash: string;
  raw_json: Record<string, unknown>;
};

export type HotspotPage = {
  items: Hotspot[];
  total: number;
  offset: number;
  limit: number;
};
export type HotspotCapabilities = {
  fetch: boolean;
  manual_add: boolean;
  discard: boolean;
  analyze: boolean;
};
export type WorkflowRun = {
  pipeline_run_id: string;
  pipeline_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  steps?: {
    step_run_id: string;
    step_key: string;
    status: string;
    error_message?: string;
    output_json?: string;
  }[];
};
