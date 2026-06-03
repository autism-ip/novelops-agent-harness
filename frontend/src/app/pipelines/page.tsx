/**
 * [INPUT]: 依赖 @/components/data-table, @/components/status-badge, @/api/types 的 PipelineRun
 * [OUTPUT]: Pipeline 列表页面（占位表格）
 * [POS]: app 路由的 /pipelines 页面
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type Column } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import type { PipelineRun } from "@/api/types";

const columns: Column<PipelineRun>[] = [
  { key: "id", label: "ID" },
  { key: "name", label: "Name" },
  {
    key: "status",
    label: "Status",
    render: (value) => <StatusBadge status={value as string} />,
  },
  { key: "created_at", label: "Created" },
  { key: "updated_at", label: "Updated" },
];

export default function PipelinesPage() {
  return (
    <div className="flex-1 p-6 space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold">Pipelines</h1>
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={columns}
            data={[]}
            emptyMessage="No pipelines yet"
          />
        </CardContent>
      </Card>
    </div>
  );
}
