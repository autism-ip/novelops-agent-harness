/**
 * [INPUT]: 依赖 @/api/client 的 apiClient, @/api/types 的 HealthResponse
 * [OUTPUT]: HealthIndicator 组件，调用后端 /api/system/health 并显示绿/红状态
 * [POS]: components 的健康探针，被 Dashboard 页面消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

"use client";

import { useEffect, useState } from "react";
import { api } from "@/api/client";
import type { HealthResponse } from "@/api/types";

export function HealthIndicator() {
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<HealthResponse>("/api/system/health")
      .then((res) => {
        if (!cancelled) setOk(res.status === "ok");
      })
      .catch(() => {
        if (!cancelled) setOk(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (ok === null) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-gray-300 animate-pulse" />
        Checking backend...
      </div>
    );
  }

  return ok ? (
    <div className="flex items-center gap-2 text-sm text-green-700">
      <span className="h-2 w-2 rounded-full bg-green-500" />
      Backend Connected
    </div>
  ) : (
    <div className="flex items-center gap-2 text-sm text-red-700">
      <span className="h-2 w-2 rounded-full bg-red-500" />
      Backend Unreachable
    </div>
  );
}
