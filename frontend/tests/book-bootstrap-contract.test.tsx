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

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); vi.unstubAllGlobals(); });

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
