/**
 * [INPUT]: 依赖 @/components/ui/badge 的 Badge 组件
 * [OUTPUT]: StatusBadge 组件，接受 status 字符串并渲染对应颜色
 * [POS]: components 的状态展示原语，被 Dashboard/Pipeline/Agent 页面消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { Badge } from "@/components/ui/badge";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-green-100 text-green-800",
  success: "bg-green-100 text-green-800",
  completed: "bg-blue-100 text-blue-800",
  failed: "bg-red-100 text-red-800",
  blocked: "bg-orange-100 text-orange-800",
  skipped: "bg-gray-100 text-gray-800",
  waiting_approval: "bg-purple-100 text-purple-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  revise: "bg-amber-100 text-amber-800",
};

const DEFAULT_COLOR = "bg-gray-100 text-gray-800";

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? DEFAULT_COLOR;
  return (
    <Badge className={`${color} border-transparent transition-colors duration-300`}>
      {status}
    </Badge>
  );
}
