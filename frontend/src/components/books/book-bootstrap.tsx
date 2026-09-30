"use client";

import Link from "next/link";
import { useRef, useState, useSyncExternalStore } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/components/hotspots/use-resource";
import { parsePendingBook, type BootstrapContext } from "./state";

const EVENT = "novelops-book-request";
function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}
function snapshot(key: string) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}

export function BookBootstrap({ coverRunId, disabled }: { coverRunId: string; disabled: boolean }) {
  const key = `novelops.books.bootstrap.${coverRunId}`;
  const pendingRaw = useSyncExternalStore(subscribe, () => snapshot(key), () => null);
  const pending = parsePendingBook(pendingRaw);
  const [bookId, setBookId] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  async function create(retry: boolean) {
    if (busy.current || disabled || (pendingRaw && !pending)) return;
    busy.current = true;
    setWorking(true);
    setError(null);
    try {
      const context = retry && pending ? pending :
        await api.get<BootstrapContext>(`/api/books/bootstrap-context/${encodeURIComponent(coverRunId)}`);
      if (context.cover_run_id !== coverRunId) throw new Error("Cover selection changed. Refresh before creating a book.");
      sessionStorage.setItem(key, JSON.stringify(context));
      window.dispatchEvent(new Event(EVENT));
      const result = await api.post<{ book: { book_id: string } }>("/api/books", context);
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
      <Button disabled={disabled || working || !!(pendingRaw && !pending)} onClick={() => void create(!!pending)}>
        {working ? "Checking selection…" : pending ? "Retry the same book request" : "Create book"}
      </Button>}
    {pending && !bookId && <p className="text-sm text-muted-foreground">The previous outcome is unconfirmed. Retry uses the same book and source IDs.</p>}
    {pendingRaw && !pending && <div role="alert" className="space-y-2 text-sm">
      <p>Saved book request is unreadable. Check Books for an existing result before clearing it.</p>
      <Button variant="outline" onClick={() => { sessionStorage.removeItem(key); window.dispatchEvent(new Event(EVENT)); }}>
        I checked the Books list
      </Button>
    </div>}
    {error && <p role="alert" className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
  </div>;
}
