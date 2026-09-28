import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

/*
 * THESIS: An editorial review desk brings the next real decision alongside its source list.
 * OWN-WORLD: Cool pearl, deep ink, cobalt actions, round surfaces, precise dividers and soft depth.
 * STORY: Inspect a signal, decide on its approved artifact, then continue into a canonical book.
 * FIRST VIEWPORT: Compact navigation above a wide list and an adjacent focused review surface.
 * FORM: User-approved composition B; .impeccable/mocks/zen-107-b-review-split.png.
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
 */

export const metadata: Metadata = {
  title: "NovelOps",
  description: "AI-assisted web-novel production system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="app-shell min-h-full font-sans">
        <template data-impeccable-contract="zen-107-b-review-split" />
        <Sidebar />
        <main id="main-content" className="min-w-0 min-h-[calc(100vh-72px)]">{children}</main>
      </body>
    </html>
  );
}
