import { WorkspaceSignIn } from "@/components/workspace-sign-in";

export default async function SignInPage({ searchParams }: {
  searchParams?: Promise<{ returnTo?: string | string[] }>
}) {
  const query = await searchParams;
  return <WorkspaceSignIn returnTo={query?.returnTo} />;
}
