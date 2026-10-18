/**
 * [INPUT]: /api/system/status and bounded/cancellable observations
 * [OUTPUT]: Separate HTTP availability, scheduler status and observed progress
 * [POS]: Dashboard and workflow workspace status; no business writes
 */
"use client";
import { useState } from "react";
import type { SystemStatus } from "@/api/types";
import { useResource, errorMessage } from "@/components/hotspots/use-resource";
import { Button } from "@/components/ui/button";

export function HealthIndicator() {
  const [revision, setRevision] = useState(0);
  const result = useResource<SystemStatus>("/api/system/status", revision, 10_000);
  const status = result.data;
  const worker = status?.worker_status;
  return <section aria-label="Execution status" className="space-y-3 text-sm">
    {result.loading && <p role="status">Checking execution…</p>}
    {result.error != null && <div role="alert"><p className="font-semibold text-destructive">Execution status unavailable</p><p>{errorMessage(result.error)}</p></div>}
    {status && <div className="space-y-2">
      <p className="font-semibold">{status.backend_status === "running" ? "Backend Connected" : "Backend Unreachable"}</p>
      <p>{worker === "running" ? "Scheduler running" : worker === "stopped" ? "Scheduler stopped" : worker === "not_started" ? "Scheduler not started" : "Scheduler status unknown"}</p>
      {status.last_error && <p className="text-destructive">Execution needs attention. Inspect workflow state before retrying a command.</p>}
      {status.last_tick && <><p className="break-words text-muted-foreground">Last tick started: {status.last_tick}</p><p>{status.active_pipeline_runs} active workflows · {status.pending_steps} pending steps · {status.failed_steps} failed steps</p></>}
    </div>}
    <Button variant="outline" size="sm" onClick={() => setRevision(v => v + 1)}>Refresh execution status</Button>
  </section>;
}
