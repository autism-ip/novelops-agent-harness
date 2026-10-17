"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useRef, useState } from "react";
import { api, ApiError } from "@/api/client";
import { errorMessage } from "@/components/hotspots/use-resource";
import { Button } from "@/components/ui/button";
import { safeWorkspaceReturn } from "@/lib/workspace-return";

export function WorkspaceSignIn({ returnTo }: { returnTo?: string | string[] }) {
  const router = useRouter();
  const target = safeWorkspaceReturn(returnTo);
  const busy = useRef(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const form = event.currentTarget;
    const password = new FormData(form).get("password");
    if (!password) { setError("Enter the workspace password."); return; }
    busy.current = true; setWorking(true); setError(null);
    try {
      await api.post("/api/auth/login", { password });
      form.reset();
      router.replace(target);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 401
        ? "Invalid workspace password. Try again." : errorMessage(cause));
      busy.current = false; setWorking(false);
    }
  }

  return <div className="page-shell app-reveal py-8 sm:py-16">
    <section className="surface mx-auto max-w-md space-y-6 p-6 sm:p-8" aria-labelledby="workspace-sign-in-title">
      <header className="space-y-3">
        <h1 id="workspace-sign-in-title" className="text-3xl font-semibold tracking-tight">Sign in to NovelOps</h1>
        <p className="text-sm leading-6 text-muted-foreground">Use your workspace password to continue. Your saved review requests stay in this browser.</p>
      </header>
      <form onSubmit={signIn} className="space-y-4" aria-busy={working}>
        <label className="block text-sm font-medium">Workspace password
          <input className="mt-2 block w-full px-3 py-2" name="password" type="password"
            autoComplete="current-password" required disabled={working} />
        </label>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" disabled={working}>{working ? "Signing in…" : "Sign in"}</Button>
      </form>
      <Button asChild variant="ghost" className="w-full"><Link prefetch={false} href={target}>Back to workspace</Link></Button>
    </section>
  </div>;
}
