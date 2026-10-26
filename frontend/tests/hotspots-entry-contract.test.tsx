import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import HotspotsPage from "../src/app/hotspots/page";
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();sessionStorage.clear();});

test("the actual hotspots route loads the real empty workbench through read-only HTTP",async()=>{
  const transport=vi.fn((url:unknown,init?:RequestInit)=>{
    const request=new Request(new URL(String(url),"http://frontend.test"),init);if(request.method!=="GET")throw new Error("Opening hotspots must not submit a command");
    if(new URL(request.url).pathname==="/api/hotspots")return Promise.resolve(Response.json({items:[],total:0,offset:0,limit:20}));
    if(new URL(request.url).pathname==="/api/hotspots/capabilities")return Promise.resolve(Response.json({fetch:false,manual_add:true,discard:true,analyze:false}));
    if(new URL(request.url).pathname==="/api/workflows")return Promise.resolve(Response.json([]));
    throw new Error(`Unexpected route read ${url}`);
  });
  vi.stubGlobal("fetch",transport);render(<HotspotsPage />);expect(await screen.findByText("No hotspot workflows yet.")).toBeTruthy();
  expect(screen.getByRole("heading",{name:"Hotspots",level:1})).toBeTruthy();expect(screen.getByRole("button",{name:"Add manually"})).toBeTruthy();
  expect(transport.mock.calls.map(([url])=>new URL(String(url),"http://frontend.test").pathname).sort()).toEqual(["/api/hotspots","/api/hotspots/capabilities","/api/workflows"].sort());
  expect(transport.mock.calls.every(([url,init])=>new Request(new URL(String(url),"http://frontend.test"),init).method==="GET")).toBe(true);
});
