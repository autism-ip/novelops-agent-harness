import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { BookDetail } from "../src/components/books/book-workspace";
const bookId = `BK-${"1".repeat(32)}`;
const path = `/api/books/${bookId}`;
const view = { book: { book_id: bookId, book_title: "Original title", genre: "Mystery", status: "ready", created_at: "2026-10-16T00:00:00Z" }, state: null, legacy: true };
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

test("idle book reads stay within one request per minute and explicit refresh uses current data", async () => {
  vi.useFakeTimers(); let current = view;
  const transport = vi.fn(async (input: unknown) => { expect(String(input)).toBe(path); return Response.json(current); });
  vi.stubGlobal("fetch", transport); render(<BookDetail bookId={bookId} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(59_999); });
  expect(screen.getByRole("heading", { name: "Original title" })).toBeTruthy();
  expect(transport).toHaveBeenCalledOnce();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(transport).toHaveBeenCalledTimes(2);
  current = { ...view, book: { ...view.book, book_title: "Updated title" } };
  fireEvent.click(screen.getByRole("button", { name: "Refresh book" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByRole("heading", { name: "Updated title" })).toBeTruthy();
  expect(transport).toHaveBeenCalledTimes(3);
});

test("slow book reads remain bounded without starting an overlapping poll", async () => {
  vi.useFakeTimers();
  const transport = vi.fn((_input: unknown, init: RequestInit) => new Promise<Response>((resolve,reject) => {
    const timer = setTimeout(() => resolve(Response.json(view)), 25_000);
    init.signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("Deadline", "AbortError")); });
  }));
  vi.stubGlobal("fetch", transport); render(<BookDetail bookId={bookId} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(24_999); });
  expect(screen.queryByRole("alert")).toBeNull(); expect(transport).toHaveBeenCalledOnce();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(screen.getByRole("heading", { name: "Original title" })).toBeTruthy();
  await act(async () => { await vi.advanceTimersByTimeAsync(59_999); });
  expect(transport).toHaveBeenCalledOnce();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(transport).toHaveBeenCalledTimes(2);
});
