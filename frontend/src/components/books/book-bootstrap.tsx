"use client";

import Link from "next/link";
import { useRef, useState, useSyncExternalStore } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/components/hotspots/use-resource";
import { parsePendingBook, type BootstrapContext } from "./state";

// Source verification and Feishu writes can exceed the generic ten-second read budget.
const BOOK_REQUEST_TIMEOUT_MS = 120_000;

const EVENT = "novelops-book-request";
const STORAGE_UNAVAILABLE = Symbol("book storage unavailable");
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}
function snapshot(key: string) {
  try { return sessionStorage.getItem(key); } catch { return STORAGE_UNAVAILABLE; }
}

export function BookBootstrap({ coverRunId, disabled }: { coverRunId: string; disabled: boolean }) {
  const key = `novelops.books.bootstrap.${coverRunId}`;
  const pendingRaw = useSyncExternalStore(subscribe, () => snapshot(key), () => null);
  const storageUnavailable = pendingRaw === STORAGE_UNAVAILABLE;
  const pending = parsePendingBook(storageUnavailable ? null : pendingRaw);
  const [bookId, setBookId] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  function assertStorage(expected: typeof pendingRaw) {
    const current = snapshot(key);
    if (current === STORAGE_UNAVAILABLE || current !== expected) {
      window.dispatchEvent(new Event(EVENT));
      throw new Error(current === STORAGE_UNAVAILABLE
        ? "Book request storage is unavailable. Restore access and check storage before continuing."
        : "Saved book request changed during this operation. Check Books before continuing with the saved request.");
    }
  }

  function clearPending() {
    if (busy.current) return;
    setError(null);
    try {
      assertStorage(pendingRaw);
      sessionStorage.removeItem(key);
      window.dispatchEvent(new Event(EVENT));
    } catch (cause) {
      setError(`Could not clear the saved book request. ${cause instanceof DOMException ? cause.message : errorMessage(cause)} Check browser storage access and try again.`);
    }
  }

  async function create(retry: boolean) {
    if (busy.current || disabled || storageUnavailable || (pendingRaw && !pending)) return;
    busy.current = true;
    setWorking(true);
    setError(null);
    try {
      assertStorage(pendingRaw);
      const context = retry && pending ? pending :
        await api.get<BootstrapContext>(`/api/books/bootstrap-context/${encodeURIComponent(coverRunId)}`, BOOK_REQUEST_TIMEOUT_MS);
      if (context.cover_run_id !== coverRunId) throw new Error("Cover selection changed. Refresh before creating a book.");
      assertStorage(pendingRaw);
      const ownedRaw = JSON.stringify(context);
      sessionStorage.setItem(key, ownedRaw);
      window.dispatchEvent(new Event(EVENT));
      const result = await api.post<{ book: { book_id: string } }>("/api/books", context, BOOK_REQUEST_TIMEOUT_MS);
      assertStorage(ownedRaw);
      sessionStorage.removeItem(key);
      window.dispatchEvent(new Event(EVENT));
      setBookId(result.book.book_id);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      busy.current = false;
      setWorking(false);
    }
  }

  return <div className="surface-soft space-y-3 p-4 sm:p-5" aria-label="Book bootstrap">
    <div>
      <h6 className="font-semibold">Start a book from this selection</h6>
      <p className="mt-1 text-sm text-muted-foreground">Create one book and its canonical StoryState v1 from the approved opportunity, title and cover.</p>
    </div>
    {bookId ? <Link className="inline-flex min-h-11 items-center rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground" href={`/books/${encodeURIComponent(bookId)}`}>Open book workspace</Link> :
      <Button disabled={disabled || working || storageUnavailable || !!(pendingRaw && !pending)} onClick={() => void create(!!pending)}>
        {working ? "Checking selection…" : pending ? "Retry the same book request" : "Create book"}
      </Button>}
    {pending && !bookId && <p className="text-sm text-muted-foreground">The previous outcome is unconfirmed. Retry uses the same book and source IDs.</p>}
    {storageUnavailable && <div role="alert" className="space-y-2 text-sm">
      <p>Cannot access saved book requests. Restore browser storage access, then check again.</p>
      <Button variant="outline" disabled={working} onClick={() => { setError(null); window.dispatchEvent(new Event(EVENT)); }}>
        Check book request storage
      </Button>
    </div>}
    {pending && !bookId && <Button variant="outline" disabled={working} onClick={clearPending}>I checked the Books list</Button>}
    {!storageUnavailable && pendingRaw && !pending && <div role="alert" className="space-y-2 text-sm">
      <p>Saved book request is unreadable. Check Books for an existing result before clearing it.</p>
      <Button variant="outline" disabled={working} onClick={clearPending}>
        I checked the Books list
      </Button>
    </div>}
    {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
  </div>;
}
