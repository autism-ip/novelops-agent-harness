import { expect, test, vi } from "vitest";
import { renderToString } from "react-dom/server";
import RootLayout from "../src/app/layout";
const current=`/books/BK-${"a".repeat(32)}`;
vi.mock("next/navigation",()=>({usePathname:()=>`/books/BK-${"a".repeat(32)}`}));

test("the actual application document preserves the writing content landmark and both navigation contexts",()=>{
  const html=renderToString(<RootLayout><article aria-label="Current chapter"><h1>Chapter 3</h1><p>Read the original prose here.</p></article></RootLayout>);
  const document=new DOMParser().parseFromString(html,"text/html");expect(document.documentElement.lang).toBe("en");
  const main=document.querySelector("main#main-content");expect(main?.querySelector("article")?.getAttribute("aria-label")).toBe("Current chapter");expect(main?.querySelector("h1")?.textContent).toBe("Chapter 3");expect(main?.textContent).toContain("Read the original prose here.");
  expect(document.querySelectorAll("main")).toHaveLength(1);
  for(const name of ["Primary","Mobile primary"]){const nav=document.querySelector(`nav[aria-label="${name}"]`)!;expect([...nav.querySelectorAll("a")].map(a=>a.getAttribute("href"))).toEqual(["/","/hotspots","/books","/pipelines","/agents"]);expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);expect(nav.querySelector('[aria-current="page"]')?.getAttribute("href")).toBe("/books");}
  const signIn=[...document.querySelectorAll("a")].find(a=>a.textContent?.trim()==="Sign in");expect(signIn?.getAttribute("href")).toBe(`/sign-in?returnTo=${encodeURIComponent(current)}`);
});
