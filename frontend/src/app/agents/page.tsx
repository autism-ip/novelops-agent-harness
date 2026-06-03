/**
 * [INPUT]: 依赖 @/components/data-table, @/components/status-badge, @/api/types 的 AgentState
 * [OUTPUT]: Agent 状态页面（占位表格）
 * [POS]: app 路由的 /agents 页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type Column } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import type { AgentState } from "@/api/types";

const columns: Column<AgentState>[] = [
  { key: "id", label: "ID" },
  { key: "agent_type", label: "Type" },
  {
    key: "status",
    label: "Status",
    render: (value) => <StatusBadge status={value as string} />,
  },
  { key: "book_id", label: "Book ID" },
  { key: "last_run_at", label: "Last Run" },
];

export default function AgentsPage() {
  return (
    <div className="flex-1 p-6 space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold">Agents</h1>
      <Card>
        <CardHeader>
          <CardTitle>Agent States</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={columns}
            data={[]}
            emptyMessage="No agents running"
          />
        </CardContent>
      </Card>
    </div>
  );
}
