"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
} from "react";
import { api, ApiError } from "@/api/client";
import type {
  Hotspot,
  HotspotPage,
  HotspotCapabilities,
  WorkflowRun,
} from "@/api/types";
import { DataTable, type Column } from "@/components/data-table";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { errorMessage, useResource } from "./use-resource";
import { ResearchHistory, ResearchResult } from "./research-results";
import {
  listPath,
  isDecisionPath,
  parsePending,
  safeSourceUrl,
  canClearRejected,
  clampOffset,
  TERMINAL,
  WORKFLOW_LABELS,
  workflowBusy,
  type Filters,
  type Pending,
  type SubmitResult,
} from "./state";

const STORAGE_KEY = "novelops.hotspots.pending";
const EVENT = "novelops-hotspot-request";
const field = "mt-1.5 block w-full rounded-xl border bg-white px-3 py-2 text-sm";
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}
function snapshot() {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}
function savePending(command: Pending | null) {
  if (command) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(command));
  else sessionStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new Event(EVENT));
}

function Detail({
  id,
  revision,
  close,
  discard,
  disabled,
  analyze,
  creative,
  books,
  submit,
}: {
  id: string;
  revision: number;
  close: () => void;
  discard: (row: Hotspot) => void;
  disabled: boolean;
  analyze: boolean;
  creative: boolean;
  books: boolean;
  submit: (command: Pending) => Promise<SubmitResult>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const result = useResource<Hotspot>(
    `/api/hotspots/${encodeURIComponent(id)}`,
    revision,
  );
  useEffect(() => {
    if (window.matchMedia("(min-width: 1024px)").matches) dialog.current?.show();
    else dialog.current?.showModal();
  }, []);
  const row = result.data;
  const sourceUrl = row && safeSourceUrl(row.url);
  return (
    <dialog
      ref={dialog}
      onClose={close}
      onCancel={close}
      aria-labelledby="hotspot-detail-title"
      className="fixed inset-y-0 left-auto right-0 m-0 h-dvh max-h-none w-full max-w-none overflow-y-auto overscroll-contain border-0 bg-background p-5 text-foreground shadow-2xl backdrop:bg-[#101f3a]/45 sm:p-7 lg:inset-y-4 lg:right-4 lg:h-auto lg:max-h-[calc(100dvh-2rem)] lg:w-[min(40vw,35rem)] lg:rounded-[1.5rem] lg:border lg:bg-white"
    >
      <div className="flex justify-between gap-4">
        <h2 id="hotspot-detail-title" className="text-xl font-semibold">
          Hotspot details
        </h2>
        <Button variant="outline" onClick={() => dialog.current?.close()}>
          Close
        </Button>
      </div>
      {result.loading && <p role="status">Loading details…</p>}
      {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
      {row && (
        <div className="mt-6 space-y-5">
          <h3 className="text-lg font-medium break-words">{row.title}</h3>
          <StatusBadge status={row.status} />
          {analyze && <ResearchHistory hotspotId={id} revision={revision} submit={submit} disabled={disabled} creative={creative} books={books} />}
          {sourceUrl && (
            <a
              className="text-sm underline"
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open source
            </a>
          )}
          <details>
            <summary className="cursor-pointer font-medium">Source details</summary>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm break-all">
              {Object.entries({
                ID: row.hotspot_id,
                Source: row.source,
                Rank: row.rank,
                Heat: row.heat_value,
                Category: row.category || "—",
                Captured: new Date(row.captured_at).toLocaleString(),
                "Dedupe key": row.dedupe_hash,
              }).map(([key, value]) => (
                <div key={key} className="contents">
                  <dt className="text-muted-foreground">{key}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
            </dl>
            <pre className="surface-soft mt-3 whitespace-pre-wrap break-all p-3 text-xs">
              {JSON.stringify(row.raw_json, null, 2)}
            </pre>
          </details>
          <Button variant="destructive" disabled={disabled || row.status === "discarded"} onClick={() => discard(row)}>
            Discard hotspot
          </Button>
        </div>
      )}
    </dialog>
  );
}

export function HotspotsWorkbench() {
  const [revision, setRevision] = useState(0);
  const [filters, setFilters] = useState<Filters>({
    source: "",
    status: "",
    from: "",
    to: "",
  });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const busy = useRef(false);
  const pendingRaw = useSyncExternalStore(subscribe, snapshot, () => null);
  const pending = parsePending(pendingRaw);
  let path: string | null = null;
  let filterError: string | null = null;
  try {
    path = listPath(filters, offset);
  } catch (cause) {
    filterError = errorMessage(cause);
  }
  const completedRun = useRef<string | null>(null);
  const onRun = useCallback((run: WorkflowRun) => {
    if (!TERMINAL.has(run.status) && run.status !== "awaiting_approval") return true;
    const marker = `${run.pipeline_run_id}:${run.status}`;
    if (completedRun.current !== marker) {
      completedRun.current = marker;
      setRevision(value => value + 1);
    }
    return !TERMINAL.has(run.status);
  }, []);
  const onListing = useCallback((page: HotspotPage) => {
    setOffset(current => clampOffset(current, page.total));
    return true;
  }, []);
  const listing = useResource<HotspotPage>(path, revision, 15000, onListing);
  const visibleSelected = selected.filter(id => listing.data?.items.some(row => row.hotspot_id === id));
  const capabilities = useResource<HotspotCapabilities>(
    "/api/hotspots/capabilities",
    revision,
  );
  const runs = useResource<WorkflowRun[]>("/api/workflows", revision, 15000);
  const current = useResource<WorkflowRun>(
    activeRun ? `/api/workflows/${encodeURIComponent(activeRun)}` : null,
    revision,
    2000,
    onRun,
  );
  const recent =
    runs.data
      ?.filter((run) => run.pipeline_type.startsWith("hotspot_") || ["title_candidates_v1", "cover_plans_v1"].includes(run.pipeline_type))
      .sort((a, b) => b.created_at.localeCompare(a.created_at)) ?? [];
  const working =
    recent.some(workflowBusy) ||
    !!(activeRun && (!current.data || workflowBusy(current.data)));
  const disabled = submitting || !!pendingRaw || working || runs.loading || !!runs.error;
  const authNeeded = [
    listing.error,
    capabilities.error,
    runs.error,
    current.error,
  ].some((e) => e instanceof ApiError && e.status === 401);
  function refresh() {
    setRevision((value) => value + 1);
  }

  async function submit(command: Pending, retry = false): Promise<SubmitResult> {
    if (busy.current || (!retry && snapshot())) return { ok: false, error: "Another request is pending. Retry the saved request first." };
    busy.current = true;
    setSubmitting(true);
    setError(null);
    try {
      savePending(command); // Persist before the POST, retaining the same key after timeout/reload.
      if (command.path === "/api/analyses") {
        const batch = await api.post<{ runs: WorkflowRun[]; errors: { hotspot_id: string; detail: string }[] }>(command.path, command.body);
        setActiveRun(batch.runs[0]?.pipeline_run_id ?? null);
        setSelected([]);
        if (batch.errors.length) setError(batch.errors.map(e => `${e.hotspot_id}: ${e.detail}`).join("; "));
      } else if (command.path.startsWith("/api/creative/") || isDecisionPath(command.path)) {
        const payload: Record<string, unknown> = { ...command.body };
        delete payload.request_key;
        const response = await api.post<WorkflowRun>(command.path, payload);
        if (!isDecisionPath(command.path)) setActiveRun(response.pipeline_run_id);
      } else {
        const run = await api.post<WorkflowRun>(command.path, command.body);
        setActiveRun(run.pipeline_run_id);
      }
      savePending(null);
      if (command.path === "/api/hotspots/manual") setManual(false);
      refresh();
      return { ok: true };
    } catch (cause) {
      // A rejected retry cannot disprove an earlier committed attempt.
      if (
        cause instanceof ApiError &&
        canClearRejected(cause.status, retry) && command.path !== "/api/analyses"
      )
        savePending(null);
      const message = errorMessage(cause);
      setError(message);
      return { ok: false, error: message };
    } finally {
      busy.current = false;
      setSubmitting(false);
    }
  }
  function discard(row: Hotspot) {
    void submit({
      path: `/api/hotspots/${encodeURIComponent(row.hotspot_id)}/discard`,
      body: { request_key: crypto.randomUUID(), expected_status: row.status },
    });
  }
  async function analyzeSelected() {
    if (busy.current || disabled || !visibleSelected.length) return;
    busy.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const items = await Promise.all(visibleSelected.map(async hotspot_id => {
        const context = await api.get<{ next_version: number; source_hash: string; can_analyze: boolean }>(`/api/hotspots/${encodeURIComponent(hotspot_id)}/research-context`);
        if (!context.can_analyze) throw new Error("A selected hotspot was discarded. Refresh the list.");
        return { hotspot_id, version: context.next_version, source_hash: context.source_hash };
      }));
      busy.current = false;
      await submit({ path: "/api/analyses", body: { request_key: crypto.randomUUID(), items } });
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      busy.current = false;
      setSubmitting(false);
    }
  }
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const outcome = await submit({
        path: "/api/hotspots/manual",
        body: {
          request_key: crypto.randomUUID(),
          title: String(values.get("title")),
          url: String(values.get("url")),
          category: String(values.get("category")),
        },
      });
    if (outcome.ok) {
      form.reset();
      setManual(false);
    }
  }
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (busy.current) return;
    busy.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/auth/login", {
        password: new FormData(form).get("password"),
      });
      form.reset();
      refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      busy.current = false;
      setSubmitting(false);
    }
  }
  function filter(key: keyof Filters, value: string) {
    setFilters({ ...filters, [key]: value });
    setOffset(0);
    setSelected([]);
  }
  const columns: Column<Hotspot>[] = [
    {
      key: "hotspot_id",
      label: "Select",
      render: (_, row) => (
        <input
          type="checkbox"
          aria-label={`Select ${row.title}`}
          checked={selected.includes(row.hotspot_id)}
          disabled={row.status === "discarded" || submitting}
          onChange={(event) =>
            setSelected((ids) =>
              event.target.checked
                ? [...ids, row.hotspot_id]
                : ids.filter((id) => id !== row.hotspot_id),
            )
          }
        />
      ),
    },
    {
      key: "title",
      label: "Hotspot",
      render: (_, row) => (
        <button
          className="max-w-lg whitespace-normal text-left font-medium underline-offset-4 hover:underline"
          onClick={() => setDetailId(row.hotspot_id)}
        >
          {row.title}
        </button>
      ),
    },
    { key: "source", label: "Source" },
    { key: "heat_value", label: "Heat" },
    {
      key: "status",
      label: "Status",
      render: (value) => <StatusBadge status={String(value)} />,
    },
    {
      key: "captured_at",
      label: "Captured",
      render: (value) => new Date(String(value)).toLocaleString(),
    },
  ];
  return (
    <div className={cn("page-shell app-reveal min-w-0 space-y-6 transition-[padding] duration-300", detailId && "review-open")}>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Hotspots</h1>
          <p className="page-intro mt-2 text-sm sm:text-base">
            Collect, inspect and select ideas for your next story.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={disabled || !capabilities.data?.fetch}
            onClick={() =>
              void submit({
                path: "/api/hotspots/fetch",
                body: { request_key: crypto.randomUUID(), limit: 50 },
              })
            }
          >
            Fetch public hotspots
          </Button>
          <Button
            variant="outline"
            disabled={disabled || !capabilities.data?.manual_add}
            onClick={() => setManual(!manual)}
          >
            Add manually
          </Button>
          <Button variant="outline" onClick={refresh}>
            Refresh
          </Button>
        </div>
      </header>
      {error && (
        <p
          role="alert"
          className="rounded-2xl border border-destructive/30 bg-red-50 p-4 text-sm text-destructive"
        >
          {error}
        </p>
      )}
      {authNeeded && (
        <form
          onSubmit={login}
          className="surface max-w-md space-y-3 p-5"
        >
          <h2 className="font-semibold">Sign in to NovelOps</h2>
          <label className="block text-sm">
            Workspace password
            <input
              className={field}
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <Button disabled={submitting}>Sign in</Button>
        </form>
      )}
      {pending && (
        <div
          role="status"
          className="surface space-y-2 border-amber-300 bg-amber-50 p-5"
        >
          <p>
            Request outcome is unconfirmed. Retry checks the same request
            without creating a second workflow.
          </p>
          <Button
            disabled={submitting || authNeeded}
            onClick={() => void submit(pending, true)}
          >
            Retry same request
          </Button>
        </div>
      )}
      {pendingRaw && !pending && (
        <div role="alert" className="surface space-y-3 border-amber-300 bg-amber-50 p-5">
          Saved request is unreadable. Review recent workflows before clearing
          it.{" "}
          <Button variant="outline" onClick={() => savePending(null)}>
            I have checked recent workflows
          </Button>
        </div>
      )}
      {manual && (
        <form onSubmit={add} className="surface space-y-4 p-5">
          <h2 className="font-semibold">New manual hotspot</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm">
              Title
              <input className={field} name="title" required maxLength={1000} />
            </label>
            <label className="text-sm">
              Source URL
              <input
                className={field}
                name="url"
                type="url"
                maxLength={2048}
                placeholder="https://… (optional)"
              />
            </label>
            <label className="text-sm">
              Category
              <input className={field} name="category" maxLength={200} />
            </label>
          </div>
          <Button disabled={disabled}>Save hotspot</Button>
          <Button
            type="button"
            variant="ghost"
            disabled={submitting}
            onClick={() => setManual(false)}
          >
            Cancel
          </Button>
        </form>
      )}
      <section
        aria-label="Hotspot filters"
        className="surface grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-4"
      >
        <label className="text-sm">
          Source
          <select
            className={field}
            value={filters.source}
            onChange={(e) => filter("source", e.target.value)}
          >
            <option value="">All sources</option>
            <option value="douyin">Douyin</option>
            <option value="manual">Manual</option>
          </select>
        </label>
        <label className="text-sm">
          Status
          <select
            className={field}
            value={filters.status}
            onChange={(e) => filter("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {["new", "normalized", "analyzed", "approved", "discarded"].map(
              (status) => (
                <option key={status}>{status}</option>
              ),
            )}
          </select>
        </label>
        <label className="text-sm">
          Captured from
          <input
            className={field}
            type="date"
            value={filters.from}
            onChange={(e) => filter("from", e.target.value)}
          />
        </label>
        <label className="text-sm">
          Captured through
          <input
            className={field}
            type="date"
            value={filters.to}
            onChange={(e) => filter("to", e.target.value)}
          />
        </label>
      </section>
      <section className="space-y-4" aria-label="Hotspot results">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm">{visibleSelected.length} selected</span>
          <Button
            variant="outline"
            disabled={disabled || !visibleSelected.length || !capabilities.data?.analyze}
            onClick={() => void analyzeSelected()}
            aria-describedby="analysis-availability"
          >
            Analyze selected
          </Button>
          <span
            id="analysis-availability"
            className="text-sm text-muted-foreground"
          >
            {capabilities.data?.analyze ? "Analyze selected ideas into story opportunities." : "Analysis is not configured for this workspace."}
          </span>
        </div>
        {capabilities.data && !capabilities.data.fetch && (
          <p className="text-sm text-muted-foreground">
            Public collection is unavailable. You can still inspect or add
            hotspots.
          </p>
        )}
        {(filterError ||
          listing.error != null ||
          capabilities.error != null) && (
          <p role="alert">
            {filterError ?? errorMessage(listing.error ?? capabilities.error)}
          </p>
        )}
        {listing.loading && <p role="status">Loading hotspots…</p>}
        {!filterError && listing.data && (
          <>
            {listing.data.items.length === 0 && <p className="surface p-6 text-sm text-muted-foreground">
              {listing.data.total > 0 ? "No hotspots on this page. Return to the previous page." : "No hotspots match these filters. Fetch public hotspots or add an idea manually."}
            </p>}
            {listing.data.items.length > 0 && <>
              <div className="grid gap-3 md:hidden">
                {listing.data.items.map(row => <article key={row.hotspot_id} className="surface scroll-mb-28 p-4">
                  <div className="flex items-start gap-3">
                    <input type="checkbox" className="mt-1 shrink-0" aria-label={`Select ${row.title}`}
                      checked={selected.includes(row.hotspot_id)} disabled={row.status === "discarded" || submitting}
                      onChange={event => setSelected(ids => event.target.checked ? [...ids, row.hotspot_id] : ids.filter(id => id !== row.hotspot_id))} />
                    <button className="min-h-11 min-w-0 flex-1 text-left font-semibold" onClick={() => setDetailId(row.hotspot_id)}>{row.title}</button>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <StatusBadge status={row.status} /><span>{row.source}</span><span>·</span><span>{new Date(row.captured_at).toLocaleDateString()}</span>
                  </div>
                </article>)}
              </div>
              <div className="hidden md:block"><DataTable columns={columns} data={listing.data.items} /></div>
            </>}
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span>
                {listing.data.total} hotspots · showing{" "}
                {listing.data.items.length ? offset + 1 : 0}–
                {listing.data.items.length ? offset + listing.data.items.length : 0}
              </span>
              <Button
                variant="outline"
                disabled={offset === 0}
                onClick={() => {
                  setOffset(Math.max(0, offset - 20));
                  setSelected([]);
                }}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                disabled={offset + 20 >= listing.data.total}
                onClick={() => {
                  setOffset(offset + 20);
                  setSelected([]);
                }}
              >
                Next
              </Button>
            </div>
          </>
        )}
      </section>
      <section
        className="surface space-y-4 p-5 sm:p-6"
        aria-label="Recent workflows"
      >
        <h2 className="font-semibold">Recent activity</h2>
        {runs.error != null && <p role="alert">{errorMessage(runs.error)}</p>}
        {runs.loading && <p role="status">Loading activity…</p>}
        {!runs.loading && !runs.error && !recent.length && (
          <p className="text-sm text-muted-foreground">
            No hotspot workflows yet.
          </p>
        )}
        <ul className="space-y-2">
          {recent.slice(0, 5).map((run) => (
            <li key={run.pipeline_run_id}>
              <button
                className="surface-soft interactive-surface flex w-full flex-wrap items-center justify-between gap-2 p-4 text-left text-sm"
                onClick={() => setActiveRun(run.pipeline_run_id)}
              >
                <span>
                  {WORKFLOW_LABELS[run.pipeline_type] ?? "Hotspot workflow"}
                  <span className="ml-2 text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </span>
                </span>
                <StatusBadge status={run.status} />
              </button>
            </li>
          ))}
        </ul>
        {activeRun && (
          <div
            className="space-y-2 border-t pt-3"
            aria-label="Selected workflow"
          >
            <p className="break-all text-xs">Run: {activeRun}</p>
            <Button variant="ghost" onClick={() => setActiveRun(null)}>Hide workflow details</Button>
            {current.loading && <p role="status">Loading workflow…</p>}
            {current.error != null && (
              <p role="alert">{errorMessage(current.error)}</p>
            )}
            {current.data && (
              <>
                <StatusBadge status={current.data.status} />
                <ol className="space-y-2">
                  {current.data.steps?.map((step) => (
                    <li key={step.step_run_id} className="text-sm">
                      <span>{step.step_key}</span>{" "}
                      <StatusBadge status={step.status} />
                      {step.error_message && (
                        <p className="mt-1 text-destructive">
                          {step.error_message} — Refresh the hotspot and review
                          the request before retrying.
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
                {current.data.pipeline_type === "hotspot_research_v1" && <ResearchResult runId={current.data.pipeline_run_id} revision={revision} />}
              </>
            )}
          </div>
        )}
      </section>
      {detailId && (
        <Detail
          key={detailId}
          id={detailId}
          revision={revision}
          close={() => setDetailId(null)}
          discard={discard}
          disabled={disabled || !capabilities.data?.discard}
          analyze={!!capabilities.data?.analyze}
          creative={!!capabilities.data?.creative}
          books={!!capabilities.data?.books}
          submit={submit}
        />
      )}
    </div>
  );
}
