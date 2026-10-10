/**
 * [INPUT]: next/link, current pathname, Lucide navigation icons
 * [OUTPUT]: compact desktop top navigation and phone/tablet bottom navigation
 * [POS]: shared NovelOps application shell
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BookOpen, House, Layers3, Radar } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: House },
  { href: "/hotspots", label: "Hotspots", icon: Radar },
  { href: "/books", label: "Books", icon: BookOpen },
  { href: "/pipelines", label: "Pipelines", icon: Layers3 },
  { href: "/agents", label: "Agents", icon: Activity },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <>
      <header className="app-nav sticky top-0 z-40 w-full">
        <div className="mx-auto flex h-[72px] max-w-[1540px] items-center justify-between gap-6 px-4 sm:px-8">
          <Link href="/" className="flex shrink-0 items-center gap-3 rounded-xl focus-visible:outline-2">
            <span aria-hidden className="flex size-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_8px_16px_-10px_#155eef]">
              <BookOpen className="size-5" strokeWidth={2.2} />
            </span>
            <span className="text-lg font-bold tracking-tight">NovelOps</span>
          </Link>
          <nav aria-label="Primary" className="hidden min-w-0 items-center gap-1 lg:flex">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return <Link key={href} href={href} aria-current={active ? "page" : undefined}
                className={cn("flex min-h-11 items-center gap-2 rounded-2xl px-3.5 text-sm font-semibold transition-colors duration-200 lg:px-4",
                  active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-white hover:text-foreground")}>
                <Icon className="size-[18px]" strokeWidth={active ? 2.3 : 1.9} aria-hidden />
                {label}
              </Link>;
            })}
          </nav>
          <div className="flex shrink-0 items-center gap-2 rounded-full border bg-white/80 px-3 py-2 text-xs font-medium text-muted-foreground">
            <span className="status-dot" aria-hidden />
            <span className="hidden sm:inline">Editor workspace</span>
            <span className="sm:hidden">Workspace</span>
          </div>
        </div>
      </header>
      <nav aria-label="Mobile primary" className="app-nav mobile-safe-bottom fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 px-1 pt-2 lg:hidden">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return <Link key={href} href={href} aria-current={active ? "page" : undefined}
            className={cn("flex min-h-[58px] flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-semibold transition-colors",
              active ? "bg-accent text-accent-foreground" : "text-muted-foreground")}>
            <Icon className="size-5" strokeWidth={active ? 2.3 : 1.9} aria-hidden />
            {label}
          </Link>;
        })}
      </nav>
    </>
  );
}
