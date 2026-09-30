"use client";

import Link from "next/link";
import { useResource, errorMessage } from "@/components/hotspots/use-resource";
import { StoryPlanning } from "./story-planning";

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
  return <div className="page-shell app-reveal space-y-6">
    <header className="space-y-2"><h1 className="page-title">Books</h1>
      <p className="page-intro">Each book begins with an approved opportunity, selected title and cover, and one canonical story state.</p></header>
    {result.loading && <p role="status">Loading books…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {result.data?.length === 0 && <div className="surface p-8"><h2 className="text-lg font-semibold">No books yet</h2>
      <p className="mt-2 text-sm text-muted-foreground">Select an opportunity, title and cover in Hotspots to create the first book.</p>
      <Link className="mt-4 inline-block text-sm font-medium underline" href="/hotspots">Go to hotspots</Link></div>}
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{result.data?.map(book =>
      <Link key={book.book_id} href={`/books/${encodeURIComponent(book.book_id)}`}
        className="surface interactive-surface group p-6 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
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
  const result = useResource<BookView>(`/api/books/${encodeURIComponent(bookId)}`, 0, 5000);
  const view = result.data;
  return <div className="page-shell app-reveal space-y-6">
    <Link href="/books" className="text-sm text-muted-foreground hover:text-foreground">← All books</Link>
    {result.loading && <p role="status">Loading book and StoryState…</p>}
    {result.error != null && <p role="alert">{errorMessage(result.error)}</p>}
    {view && <>
      <header className="surface p-6 sm:p-8">
        <h1 className="page-title">{view.book.book_title}</h1>
        <p className="mt-3 text-muted-foreground">{view.book.genre}</p>
        <p className="mt-5 inline-flex rounded-full bg-accent px-3 py-1.5 text-xs font-semibold text-accent-foreground">{view.state ? `Canonical StoryState · v${view.state.version}` : view.legacy ? "Legacy book" : "Initialization in progress"}</p>
      </header>
      {!view.state && <p className="surface p-5 text-sm text-muted-foreground">{view.legacy ? "This book predates canonical StoryState. Its legacy record is readable; it has not been migrated." : "Book initialization has not reached a ready canonical state. Retry the original creation request from the selected cover."}</p>}
      {view.state && <><StoryPlanning bookId={bookId} approvedBible={Boolean(view.state.content.StoryBible?.bible_artifact_id)} />
      <div className="grid gap-4 md:grid-cols-2">{Object.entries(view.state.content).map(([namespace, fields]) =>
        <section key={namespace} className="surface min-w-0 p-5 sm:p-6">
          <h2 className="text-lg font-semibold">{namespace.replace(/([a-z])([A-Z])/g, "$1 $2")}</h2>
          <dl className="mt-4 space-y-3">{Object.entries(fields).map(([name, value]) =>
            <div key={name} className="text-sm"><dt className="font-medium text-muted-foreground">{name.replaceAll("_", " ")}</dt>
              <dd className="mt-1 break-words">{summary(value)}</dd></div>)}</dl>
        </section>)}</div>
      <details className="surface p-5 text-sm"><summary className="min-h-11 cursor-pointer font-medium">Version and source provenance</summary>
        <dl className="mt-4 space-y-2 break-all"><div><dt>State ID</dt><dd>{view.state.story_state_id}</dd></div>
          <div><dt>Artifact ID</dt><dd>{view.state.artifact_id}</dd></div>
          <div><dt>Content SHA-256</dt><dd>{view.state.content_hash}</dd></div>
          <div><dt>Source artifacts</dt><dd>{view.state.source_refs.join(" · ")}</dd></div>
          <div><dt>Initialized</dt><dd>{new Date(view.state.created_at).toLocaleString()}</dd></div></dl>
      </details></>}
    </>}
  </div>;
}
