/**
 * [INPUT]: 依赖 @/components/ui/badge 的 Badge 组件
 * [OUTPUT]: StatusBadge 组件，接受 status 字符串并渲染对应颜色
 * [POS]: components 的状态展示原语，被 Dashboard/Pipeline/Agent 页面消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { Badge } from "@/components/ui/badge";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-900",
  running: "bg-blue-100 text-blue-900",
  success: "bg-emerald-100 text-emerald-900",
  completed: "bg-blue-100 text-blue-900",
  failed: "bg-red-100 text-red-900",
  blocked: "bg-orange-100 text-orange-900",
  skipped: "bg-slate-100 text-slate-800",
  waiting_approval: "bg-violet-100 text-violet-900",
  awaiting_approval: "bg-violet-100 text-violet-900",
  approved: "bg-emerald-100 text-emerald-900",
  rejected: "bg-red-100 text-red-900",
  revise: "bg-amber-100 text-amber-900",
  ready: "bg-emerald-100 text-emerald-900",
  initializing: "bg-amber-100 text-amber-900",
  discarded: "bg-slate-100 text-slate-800",
};

const DEFAULT_COLOR = "bg-slate-100 text-slate-800";

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? DEFAULT_COLOR;
  return (
    <Badge className={`${color} border-transparent px-3 py-1.5 text-xs font-semibold transition-colors duration-300`}>
      {status}
    </Badge>
  );
}
