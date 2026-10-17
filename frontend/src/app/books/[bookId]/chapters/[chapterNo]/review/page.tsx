import { notFound } from "next/navigation";
import { FocusedChapterReview } from "@/components/books/focused-chapter-review";

export default async function ChapterReviewPage({ params }: {
  params: Promise<{ bookId: string; chapterNo: string }>
}) {
  const { bookId, chapterNo } = await params;
  if (!/^[A-Za-z0-9_-]{1,200}$/.test(bookId) || !/^[1-9]\d{0,4}$/.test(chapterNo) || Number(chapterNo) > 10000) {
    notFound();
  }
  return <FocusedChapterReview bookId={bookId} chapterNo={Number(chapterNo)} />;
}
