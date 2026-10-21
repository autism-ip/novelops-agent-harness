import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SignInPage from "../src/app/sign-in/page";
import { Sidebar } from "../src/components/sidebar";
import { safeWorkspaceReturn } from "../src/lib/workspace-return";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), pathname: "/books/BK-example/chapters/1/review" }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname,
  useRouter: () => ({ replace: navigation.replace }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); navigation.replace.mockClear(); navigation.pathname = "/books/BK-example/chapters/1/review"; sessionStorage.clear(); });

const destination = "/books/BK-example/chapters/1/review";
test.each(["/", "/books", "/hotspots", "/pipelines", "/agents", "/books/BK-example", destination,
  `/books/${"a".repeat(200)}/chapters/10000/review`])("return path preserves known local workspace route %s", path => {
  expect(safeWorkspaceReturn(path)).toBe(path);
});
test.each([undefined, null, [], [destination], "", "https://example.com", "//example.com", "/\\example.com",
  "javascript:alert(1)", "/books/../api/system", "/books/%2fexample", "/books/BK-example?next=//example.com",
  "/sign-in", "/api/auth/login", "/books/BK-example#token", "/books/BK-example\n", `/books/${"a".repeat(201)}`,
  "/books/BK-example/chapters/0/review", "/books/BK-example/chapters/01/review", "/books/BK-example/chapters/10001/review"])(
  "untrusted return path falls back safely (%s)", path => expect(safeWorkspaceReturn(path)).toBe("/books"));

test("global workspace access points back to the exact book chapter", () => {
  render(<Sidebar />);
  expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toBe(`/sign-in?returnTo=${encodeURIComponent(destination)}`);
});

test("sign-in posts once, clears only the password and returns to the original review", async () => {
  let resolve!: (response: Response) => void;
  const transport = vi.fn<(input: unknown, init: RequestInit) => Promise<Response>>(() => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal("fetch", transport);
  const pending = '{"exact":"unknown-outcome-command"}'; sessionStorage.setItem("novelops.chapter-review.pending.BK-example.1", pending);
  render(await SignInPage({ searchParams: Promise.resolve({ returnTo: destination }) }));
  const input = screen.getByLabelText("Workspace password") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "synthetic-password" } });
  const form = input.closest("form")!; fireEvent.submit(form); fireEvent.submit(form);
  expect(transport).toHaveBeenCalledOnce();
  expect(screen.getByRole("button", { name: "Signing in…" })).toHaveProperty("disabled", true);
  expect(transport.mock.calls[0][0]).toBe("/api/auth/login");
  expect(JSON.parse(String(transport.mock.calls[0][1].body))).toEqual({ password: "synthetic-password" });
  resolve(Response.json({ detail: "Login successful" }));
  await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith(destination));
  expect(input.value).toBe("");
  expect(sessionStorage.getItem("novelops.chapter-review.pending.BK-example.1")).toBe(pending);
  expect(JSON.stringify([...Array(sessionStorage.length)].map((_,i)=>sessionStorage.getItem(sessionStorage.key(i)!)))).not.toContain("synthetic-password");
});

test.each([401, 503])("failed login %s gives an actionable error and permits correction", async status => {
  const transport = vi.fn().mockResolvedValueOnce(Response.json({ detail: "Server configuration error" }, { status })).mockResolvedValueOnce(Response.json({ detail: "Login successful" })); vi.stubGlobal("fetch", transport);
  render(await SignInPage({}));
  fireEvent.change(screen.getByLabelText("Workspace password"), { target: { value: "synthetic-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toBe(status === 401 ? "Invalid workspace password. Try again." : "Server configuration error");
  expect(navigation.replace).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Sign in" })).toHaveProperty("disabled", false);
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/books"));
});

test("connection failure preserves the form and a blank submission never sends credentials", async () => {
  const transport = vi.fn().mockRejectedValue(new Error("Connection lost")); vi.stubGlobal("fetch", transport);
  render(await SignInPage({ searchParams: Promise.resolve({ returnTo: [destination] }) }));
  fireEvent.submit(screen.getByLabelText("Workspace password").closest("form")!);
  expect(await screen.findByText("Enter the workspace password.")).toBeTruthy(); expect(transport).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Workspace password"), { target: { value: "synthetic-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Connection lost");
  expect(screen.getByLabelText("Workspace password")).toHaveProperty("value", "synthetic-password");
  expect(navigation.replace).not.toHaveBeenCalled();
});
