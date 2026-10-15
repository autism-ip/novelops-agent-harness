import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { BookBootstrap } from "../src/components/books/book-bootstrap";

const coverRun = `PR-${"1".repeat(32)}`;
const bookId = `BK-${"2".repeat(32)}`;
const key = `novelops.books.bootstrap.${coverRun}`;
const context = { book_id: bookId, cover_run_id: coverRun,
  cover_artifact_id: `AR-${"3".repeat(32)}`, title_artifact_id: `AR-${"4".repeat(32)}`,
  opportunity_artifact_id: `AR-${"5".repeat(32)}` };

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); sessionStorage.clear(); vi.unstubAllGlobals(); });

function serve() {
  const transport = vi.fn((...[, init]: [unknown, RequestInit]) => Promise.resolve(
    Response.json(init.method === "POST" ? { book: { book_id: bookId } } : context)));
  vi.stubGlobal("fetch", transport);
  return transport;
}

test.each(["{unreadable", "[]"])("failed checked-history clear preserves malformed book intent: %s", async saved => {
  sessionStorage.setItem(key, saved);
  const transport = serve();
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  expect((screen.getByRole("button", { name: "Create book" }) as HTMLButtonElement).disabled).toBe(true);
  const remove = vi.spyOn(Object.getPrototypeOf(sessionStorage), "removeItem")
    .mockImplementation(() => { throw new Error("Browser storage unavailable"); });
  fireEvent.click(screen.getByRole("button", { name: "I checked the Books list" }));
  expect(await screen.findByText("Could not clear the saved book request. Browser storage unavailable Check browser storage access and try again.")).toHaveProperty("role", "alert");
  expect(sessionStorage.getItem(key)).toBe(saved);
  expect(transport).not.toHaveBeenCalled();
  remove.mockRestore();
  fireEvent.click(screen.getByRole("button", { name: "I checked the Books list" }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect(screen.queryByText(/Could not clear the saved book request/)).toBeNull();
  expect((screen.getByRole("button", { name: "Create book" }) as HTMLButtonElement).disabled).toBe(false);
});

test("create uses exact approved context and opens the returned canonical book", async () => {
  const transport = serve();
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Create book" }));
  const link = await screen.findByRole("link", { name: "Open book workspace" });
  expect(link.getAttribute("href")).toBe(`/books/${bookId}`);
  expect(transport).toHaveBeenCalledTimes(2);
  const [read, write] = transport.mock.calls;
  expect(read[0]).toBe(`/api/books/bootstrap-context/${coverRun}`);
  expect(new Request(`http://localhost${read[0]}`, read[1]).method).toBe("GET");
  expect(write[0]).toBe("/api/books");
  expect(write[1].method).toBe("POST");
  expect(JSON.parse(String(write[1].body))).toEqual(context);
  expect(write[1].headers).not.toHaveProperty("x-api-key");
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("an unknown POST outcome retries identical book and source IDs without rereading context", async () => {
  let fail = true;
  const transport = vi.fn((...[, init]: [unknown, RequestInit]) => Promise.resolve(
    init.method === "POST" && fail ? Response.json({ detail: "Save outcome unknown" }, { status: 503 }) :
      Response.json(init.method === "POST" ? { book: { book_id: bookId } } : context)));
  vi.stubGlobal("fetch", transport);
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Create book" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Save outcome unknown");
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context));
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  await screen.findByRole("link", { name: "Open book workspace" });
  const writes = transport.mock.calls.filter(([, init]) => init.method === "POST");
  expect(writes).toHaveLength(2);
  expect(writes[0][1].body).toBe(writes[1][1].body);
  expect(transport.mock.calls.filter(([, init]) => init.method !== "POST")).toHaveLength(1);
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("a persisted request from a different cover is rejected before any HTTP call", async () => {
  const saved = { ...context, cover_run_id: `PR-${"6".repeat(32)}` };
  sessionStorage.setItem(key, JSON.stringify(saved));
  const transport = serve();
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Cover selection changed. Refresh before creating a book.");
  expect(transport).not.toHaveBeenCalled();
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(saved));
});

test("a changed fresh selection is rejected rather than becoming a book command", async () => {
  const transport = vi.fn(() => Promise.resolve(Response.json({ ...context, cover_run_id: `PR-${"6".repeat(32)}` })));
  vi.stubGlobal("fetch", transport);
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Create book" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Cover selection changed. Refresh before creating a book.");
  expect(transport).toHaveBeenCalledTimes(1);
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("failed storage persistence prevents an untracked book write", async () => {
  const transport = serve();
  vi.spyOn(Object.getPrototypeOf(sessionStorage), "setItem").mockImplementation(() => { throw new Error("Cannot preserve request"); });
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Create book" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Cannot preserve request");
  expect(transport).toHaveBeenCalledTimes(1);
  expect(transport.mock.calls[0][1].method).not.toBe("POST");
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("storage clear failure after a completed POST preserves the exact request for idempotent recovery", async () => {
  sessionStorage.setItem(key, JSON.stringify(context));
  const transport = serve();
  const remove = vi.spyOn(Object.getPrototypeOf(sessionStorage), "removeItem")
    .mockImplementation(() => { throw new Error("Cannot clear result"); });
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Cannot clear result");
  expect(screen.queryByRole("link", { name: "Open book workspace" })).toBeNull();
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context));
  remove.mockRestore();
  fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  await screen.findByRole("link", { name: "Open book workspace" });
  expect(transport).toHaveBeenCalledTimes(2);
  expect(transport.mock.calls[0][1].body).toBe(transport.mock.calls[1][1].body);
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("a pending book write shows progress and cannot be double submitted", async () => {
  sessionStorage.setItem(key, JSON.stringify(context));
  let finish!: (response: Response) => void;
  const transport = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
  vi.stubGlobal("fetch", transport);
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  const progress = await screen.findByRole("button", { name: "Checking selection…" });
  expect((progress as HTMLButtonElement).disabled).toBe(true);
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context));
  fireEvent.click(progress);
  expect(transport).toHaveBeenCalledOnce();
  await act(async () => finish(Response.json({ book: { book_id: bookId } })));
  await screen.findByRole("link", { name: "Open book workspace" });
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("disabled creation and server rendering do not send or leak a tab-local command", () => {
  sessionStorage.setItem(key, JSON.stringify(context));
  const transport = serve();
  const html = renderToString(<BookBootstrap coverRunId={coverRun} disabled={true} />);
  expect(html).not.toContain(bookId);
  expect(html).not.toContain("Retry the same book request");
  render(<BookBootstrap coverRunId={coverRun} disabled={true} />);
  const button = screen.getByRole("button", { name: "Retry the same book request" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(button);
  expect(transport).not.toHaveBeenCalled();
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context));
});

function readBoundary() {
  const nativeGet = Storage.prototype.getItem;
  let denied = true;
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(function (this: Storage, name: string) {
    if (name === key && denied) throw new DOMException("Native read denied", "SecurityError");
    return nativeGet.call(this, name);
  });
  return { allow: () => { denied = false; }, deny: () => { denied = true; }, peek: () => nativeGet.call(sessionStorage, key) };
}
for (const saved of [JSON.stringify(context), "{unreadable"]) {
  test(`unavailable book storage preserves saved bytes until a public recheck: ${saved.startsWith("{unreadable") ? "malformed" : "valid"}`, async () => {
    sessionStorage.setItem(key, saved); const boundary = readBoundary(), transport = serve();
    render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
    await screen.findByText(/Cannot access saved book requests/);
    expect((screen.getByRole("button", { name: "Create book" }) as HTMLButtonElement).disabled).toBe(true);
    expect(boundary.peek()).toBe(saved); expect(transport).not.toHaveBeenCalled();
    boundary.allow(); fireEvent.click(screen.getByRole("button", { name: "Check book request storage" }));
    if (saved === JSON.stringify(context)) {
      fireEvent.click(await screen.findByRole("button", { name: "Retry the same book request" }));
      await screen.findByRole("link", { name: "Open book workspace" });
      expect(transport).toHaveBeenCalledOnce(); expect(transport.mock.calls[0][1].method).toBe("POST");
      expect(JSON.parse(String(transport.mock.calls[0][1].body))).toEqual(context);
    } else {
      await screen.findByText(/Saved book request is unreadable/);
      expect(boundary.peek()).toBe(saved); expect(transport).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole("button", { name: "I checked the Books list" }));
      expect(boundary.peek()).toBeNull();
    }
  });
}

test("read failure after render blocks creation and preserves the newly saved exact request", async () => {
  const transport = serve(); render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  sessionStorage.setItem(key, JSON.stringify(context)); const boundary = readBoundary();
  fireEvent.click(screen.getByRole("button", { name: "Create book" }));
  await screen.findByText(/Cannot access saved book requests/);
  expect(transport).not.toHaveBeenCalled(); expect(boundary.peek()).toBe(JSON.stringify(context));
  boundary.allow(); fireEvent.click(screen.getByRole("button", { name: "Check book request storage" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry the same book request" }));
  await screen.findByRole("link", { name: "Open book workspace" });
  expect(transport).toHaveBeenCalledOnce(); expect(JSON.parse(String(transport.mock.calls[0][1].body))).toEqual(context);
});

for (const during of ["read denied", "intent changed"]) {
  test(`${during} during context preparation prevents replacing another saved book request`, async () => {
    let finish!: (response: Response) => void;
    const transport = vi.fn((_input: unknown, init: RequestInit) => init.method === "POST" ? Promise.resolve(Response.json({ book: { book_id: bookId } })) : new Promise<Response>(resolve => { finish = resolve; }));
    vi.stubGlobal("fetch", transport); render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Create book" }));
    await waitFor(() => expect(transport).toHaveBeenCalledOnce());
    sessionStorage.setItem(key, JSON.stringify(context)); const boundary = readBoundary();
    if (during === "intent changed") boundary.allow();
    await act(async () => finish(Response.json({ ...context, book_id: `BK-${"6".repeat(32)}` })));
    await screen.findByText(during === "read denied" ? /Book request storage is unavailable/ : /Saved book request changed during this operation/);
    expect(boundary.peek()).toBe(JSON.stringify(context)); expect(transport.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(0);
    boundary.allow(); if (during === "read denied") fireEvent.click(screen.getByRole("button", { name: "Check book request storage" }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry the same book request" }));
    await screen.findByRole("link", { name: "Open book workspace" });
    expect(transport).toHaveBeenCalledTimes(2); expect(JSON.parse(String(transport.mock.calls[1][1].body))).toEqual(context);
  });
}

test("confirmed book completion cannot clear a different intent saved while the POST was pending", async () => {
  sessionStorage.setItem(key, JSON.stringify(context)); let finish!: (response: Response) => void;
  const transport = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })); vi.stubGlobal("fetch", transport);
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />); fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  await waitFor(() => expect(transport).toHaveBeenCalledOnce());
  const newer = JSON.stringify({ ...context, book_id: `BK-${"7".repeat(32)}` }); sessionStorage.setItem(key, newer);
  await act(async () => finish(Response.json({ book: { book_id: bookId } })));
  await screen.findByText(/Saved book request changed during this operation/);
  expect(sessionStorage.getItem(key)).toBe(newer); expect(transport).toHaveBeenCalledOnce(); expect(screen.queryByRole("link", { name: "Open book workspace" })).toBeNull();
});

test("a checked Books list can release valid uncertain intent and preserves native clear failures", async () => {
  sessionStorage.setItem(key, JSON.stringify(context)); const transport = serve(); render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  const remove = vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("Native clear denied", "SecurityError"); });
  fireEvent.click(screen.getByRole("button", { name: "I checked the Books list" }));
  await screen.findByText(/Could not clear the saved book request.*Native clear denied/);
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context)); expect(transport).not.toHaveBeenCalled();
  remove.mockRestore(); fireEvent.click(screen.getByRole("button", { name: "I checked the Books list" }));
  await waitFor(() => expect(sessionStorage.getItem(key)).toBeNull());
  expect((screen.getByRole("button", { name: "Create book" }) as HTMLButtonElement).disabled).toBe(false);
});


function delayedResponse(value: unknown, delay: number, signal?: AbortSignal | null) {
  return new Promise<Response>((resolve, reject) => {
    const timer = setTimeout(() => resolve(Response.json(value)), delay);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Request deadline", "AbortError"));
    }, { once: true });
  });
}

test("slow verified source and book writes finish without abandoning the frozen command", async () => {
  vi.useFakeTimers();
  const transport = vi.fn((...[, init]: [unknown, RequestInit]) =>
    delayedResponse(init.method === "POST" ? { book: { book_id: bookId } } : context,
      init.method === "POST" ? 119_000 : 23_000, init.signal));
  vi.stubGlobal("fetch", transport);
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Create book" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(10_001); });
  expect(screen.queryByRole("alert")).toBeNull();
  expect((screen.getByRole("button", { name: "Checking selection…" }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(13_000); });
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context));
  expect(transport).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(118_999); });
  expect(screen.getByRole("link", { name: "Open book workspace" }).getAttribute("href")).toBe(`/books/${bookId}`);
  expect(transport).toHaveBeenCalledTimes(2);
  expect(sessionStorage.getItem(key)).toBeNull();
});

test("the bounded book deadline retains the exact request and requires an explicit retry", async () => {
  vi.useFakeTimers();
  sessionStorage.setItem(key, JSON.stringify(context));
  const transport = vi.fn((...[, init]: [unknown, RequestInit]) => delayedResponse({}, 121_000, init.signal));
  vi.stubGlobal("fetch", transport);
  render(<BookBootstrap coverRunId={coverRun} disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry the same book request" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(119_999); });
  expect(screen.queryByRole("alert")).toBeNull();
  await act(async () => { await vi.advanceTimersByTimeAsync(2); });
  expect(screen.getByRole("alert").textContent).toMatch(/Request timed out/);
  expect(sessionStorage.getItem(key)).toBe(JSON.stringify(context));
  expect((screen.getByRole("button", { name: "Retry the same book request" }) as HTMLButtonElement).disabled).toBe(false);
  expect(transport).toHaveBeenCalledOnce();
  expect(transport.mock.calls[0][1].body).toBe(JSON.stringify(context));
});
