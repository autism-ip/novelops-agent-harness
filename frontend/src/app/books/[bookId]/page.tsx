import { BookDetail } from "@/components/books/book-workspace";

export default async function BookPage({ params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = await params;
  return <BookDetail bookId={bookId} />;
}
