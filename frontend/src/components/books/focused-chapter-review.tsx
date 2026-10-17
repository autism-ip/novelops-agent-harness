"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChapterReviewDesk } from "./chapter-review-desk";

export function FocusedChapterReview({ bookId, chapterNo }: { bookId: string; chapterNo: number }) {
  const [revision, setRevision] = useState(0);
  return <div className="page-shell app-reveal space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-3">
        <Button asChild variant="ghost" className="-ml-4"><Link prefetch={false} href={`/books/${encodeURIComponent(bookId)}`}>
          <ArrowLeft aria-hidden="true" />Back to book
        </Link></Button>
        <h1 className="page-title">Chapter {chapterNo} review</h1>
        <p className="page-intro">Read the draft and its sources, record your decision, then lock the approved version.</p>
      </div>
      <Button variant="outline" onClick={() => setRevision(value => value + 1)}>Refresh review</Button>
    </header>
    <section className="surface p-5 sm:p-6" aria-label={`Chapter ${chapterNo} editorial review`}>
      <ChapterReviewDesk bookId={bookId} chapterNo={chapterNo} refresh={revision}
        onChanged={() => setRevision(value => value + 1)} headingLevel={2} className="border-t-0 pt-0" />
    </section>
  </div>;
}
