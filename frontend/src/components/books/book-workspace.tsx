"use client";

import Link from "next/link";
import { useResource, errorMessage } from "@/components/hotspots/use-resource";

type Book = {
  book_id: string;
  book_title: string;
  genre: string;
  created_at: string;
  status: string;
  story_state_version?: number;
  story_state_hash?: string;
};
type StoryState = {
  story_state_id: string;
  version: number;
  artifact_id: string;
  content_hash: string;
  source_refs: string[];
  created_at: string;
  content: Record<string, Record<string, unknown>>;
};
type BookView = { book: Book; state: StoryState | null; legacy?: boolean };

export function BookList() {
  const result = useResource<Book[]>("/api/books", 0);
  return <div className="flex-1 space-y-6 p-5 pt-16 sm:p-8 md:pt-8">
    <header className="space-y-2"><p className="text-sm font-medium text-muted-foreground">Story workspace</p>
      <h1 className="text-3xl font-semibold tracking-tight">Books</h1>
      <p className="max-w-2xl text-muted-foreground">Each book begins with an approved opportunity, selected title and cover, and one canonical story state.</p></header>
    {result.loading && <p role="status">Loading books…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.data?.length === 0 && <div className="rounded-3xl border bg-card p-8"><h2 className="text-lg font-semibold">No books yet</h2>
      <p className="mt-2 text-sm text-muted-foreground">Select an opportunity, title and cover in Hotspots to create the first book.</p>
      <Link className="mt-4 inline-block text-sm font-medium underline" href="/hotspots">Go to hotspots</Link></div>}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{result.data?.map(book =>
      <Link key={book.book_id} href={`/books/${encodeURIComponent(book.book_id)}`}
        className="group rounded-3xl border bg-card p-6 transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring motion-reduce:transform-none">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{book.story_state_version ? `StoryState v${book.story_state_version}` : "Legacy book"} · {book.status}</p>
        <h2 className="mt-3 text-xl font-semibold tracking-tight group-hover:text-primary">{book.book_title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{book.genre || "Genre to be developed"}</p>
        <p className="mt-5 text-xs text-muted-foreground">Created {new Date(book.created_at).toLocaleDateString()}</p>
      </Link>)}</div>
  </div>;
}

function summary(value: unknown): string {
  if (typeof value === "string") return value || "Not defined yet";
  if (Array.isArray(value)) return value.length ? value.map(String).join(" · ") : "Not defined yet";
  return value == null ? "Not defined yet" : JSON.stringify(value);
}

export function BookDetail({ bookId }: { bookId: string }) {
  const result = useResource<BookView>(`/api/books/${encodeURIComponent(bookId)}`, 0);
  const view = result.data;
  return <div className="flex-1 space-y-6 p-5 pt-16 sm:p-8 md:pt-8">
    <Link href="/books" className="text-sm text-muted-foreground hover:text-foreground">← All books</Link>
    {result.loading && <p role="status">Loading book and StoryState…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {view && <>
      <header className="rounded-3xl border bg-card p-6 sm:p-8">
        <p className="text-sm font-medium text-muted-foreground">{view.state ? `Canonical story workspace · v${view.state.version}` : view.legacy ? "Legacy book" : "Initialization in progress"}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{view.book.book_title}</h1>
        <p className="mt-3 text-muted-foreground">{view.book.genre}</p>
      </header>
      {!view.state && <p className="rounded-2xl border bg-card p-5 text-sm text-muted-foreground">{view.legacy ? "This book predates canonical StoryState. Its legacy record is readable; it has not been migrated." : "Book initialization has not reached a ready canonical state. Retry the original creation request from the selected cover."}</p>}
      {view.state && <><div className="grid gap-4 md:grid-cols-2">{Object.entries(view.state.content).map(([namespace, fields]) =>
        <section key={namespace} className="min-w-0 rounded-3xl border bg-card p-5 sm:p-6">
          <h2 className="text-lg font-semibold">{namespace.replace(/([a-z])([A-Z])/g, "$1 $2")}</h2>
          <dl className="mt-4 space-y-3">{Object.entries(fields).map(([name, value]) =>
            <div key={name} className="text-sm"><dt className="font-medium text-muted-foreground">{name.replaceAll("_", " ")}</dt>
              <dd className="mt-1 break-words">{summary(value)}</dd></div>)}</dl>
        </section>)}</div>
      <details className="rounded-2xl border bg-card p-5 text-sm"><summary className="cursor-pointer font-medium">Version and source provenance</summary>
        <dl className="mt-4 space-y-2 break-all"><div><dt>State ID</dt><dd>{view.state.story_state_id}</dd></div>
          <div><dt>Artifact ID</dt><dd>{view.state.artifact_id}</dd></div>
          <div><dt>Content SHA-256</dt><dd>{view.state.content_hash}</dd></div>
          <div><dt>Source artifacts</dt><dd>{view.state.source_refs.join(" · ")}</dd></div>
          <div><dt>Initialized</dt><dd>{new Date(view.state.created_at).toLocaleString()}</dd></div></dl>
      </details></>}
    </>}
  </div>;
}
