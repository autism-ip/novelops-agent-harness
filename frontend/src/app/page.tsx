/**
 * [INPUT]: HealthIndicator and real app routes
 * [OUTPUT]: dashboard with truthful workflow entry points and backend state
 * [POS]: app home
 */
import Link from "next/link";
import { ArrowRight, BookOpen, Radar, ShieldCheck } from "lucide-react";
import { HealthIndicator } from "@/components/health-indicator";

const nextSteps = [
  { href: "/hotspots", icon: Radar, title: "Review hotspots", description: "Inspect source signals, request analysis and make approval decisions." },
  { href: "/books", icon: BookOpen, title: "Open books", description: "Read canonical StoryState and trace the selected source artifacts." },
] as const;

export default function DashboardPage() {
  return (
    <div className="page-shell app-reveal space-y-8">
      <header className="max-w-3xl space-y-4 pt-2 sm:pt-6">
        <h1 className="page-title">Keep the story moving.</h1>
        <p className="page-intro text-base sm:text-lg">
          Move from a public signal to an approved story direction, then keep every book grounded in one versioned story state.
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,.7fr)]">
        <section className="surface overflow-hidden p-6 sm:p-8" aria-labelledby="workflow-heading">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="workflow-heading" className="text-xl font-semibold sm:text-2xl">Your editorial path</h2>
            <span className="rounded-full bg-accent px-3 py-1.5 text-xs font-semibold text-accent-foreground">Source to StoryState</span>
          </div>
          <ol className="mt-7 grid gap-3 md:grid-cols-3">
            <li className="surface-soft p-5">
              <span className="text-sm font-semibold text-primary">Research</span>
              <p className="mt-2 font-semibold">Inspect the signal</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">Review source details and analysis before choosing an opportunity.</p>
            </li>
            <li className="surface-soft p-5">
              <span className="text-sm font-semibold text-primary">Decide</span>
              <p className="mt-2 font-semibold">Approve a direction</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">Select a title and cover with exact version and artifact provenance.</p>
            </li>
            <li className="surface-soft p-5">
              <span className="text-sm font-semibold text-primary">Build</span>
              <p className="mt-2 font-semibold">Begin the book</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">Initialize one canonical StoryState from the approved chain.</p>
            </li>
          </ol>
          <Link href="/hotspots" className="mt-7 inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-white transition-transform hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring motion-reduce:transform-none">
            Open hotspots <ArrowRight className="size-4" aria-hidden />
          </Link>
        </section>
        <section className="surface flex flex-col justify-between gap-8 p-6 sm:p-8" aria-labelledby="system-heading">
          <div>
            <ShieldCheck className="size-7 text-primary" aria-hidden />
            <h2 id="system-heading" className="mt-5 text-xl font-semibold">Workspace status</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Check the backend connection before beginning a review.</p>
          </div>
          <HealthIndicator />
        </section>
      </div>

      <section aria-labelledby="continue-heading">
        <h2 id="continue-heading" className="mb-4 text-xl font-semibold">Continue working</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {nextSteps.map(({ href, icon: Icon, title, description }) => (
            <Link key={href} href={href} className="surface interactive-surface group flex items-start gap-4 p-5 sm:p-6">
              <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-accent text-primary"><Icon className="size-5" aria-hidden /></span>
              <span className="min-w-0 flex-1"><span className="block text-lg font-semibold">{title}</span><span className="mt-1 block text-sm leading-6 text-muted-foreground">{description}</span></span>
              <ArrowRight className="mt-1 size-4 text-primary transition-transform group-hover:translate-x-1 motion-reduce:transform-none" aria-hidden />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
