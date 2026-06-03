/**
 * [INPUT]: 依赖 @/components/health-indicator, @/components/ui/card
 * [OUTPUT]: Dashboard 页面组件（健康检查 + 占位卡片）
 * [POS]: app 路由的首页，展示系统概览
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { HealthIndicator } from "@/components/health-indicator";

export default function DashboardPage() {
  return (
    <div className="flex-1 p-6 space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Health Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Backend Status</CardTitle>
            <CardDescription>Connectivity check</CardDescription>
          </CardHeader>
          <CardContent>
            <HealthIndicator />
          </CardContent>
        </Card>

        {/* Pipelines Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Pipelines</CardTitle>
            <CardDescription>Active pipeline runs</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">0</p>
            <p className="text-xs text-muted-foreground">No pipelines yet</p>
          </CardContent>
        </Card>

        {/* Agents Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Agents</CardTitle>
            <CardDescription>Running agents</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">0</p>
            <p className="text-xs text-muted-foreground">No agents running</p>
          </CardContent>
        </Card>

        {/* Activity Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
            <CardDescription>Latest events</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">No recent activity</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
