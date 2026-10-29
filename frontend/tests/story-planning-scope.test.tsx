import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StoryPlanning } from "../src/components/books/story-planning";
const book=`BK-${"a".repeat(32)}`,otherBook=`BK-${"b".repeat(32)}`,run=`PR-${"c".repeat(32)}`;
const artifact=`AR-${"d".repeat(32)}`,key=`novelops.story-planning.pending.${book}`;
function command(bookId: string,chapterNo: number|null) {return chapterNo===null ? {
  path:`/api/books/${bookId}/bibles`,body:{book_id:bookId,base_state_artifact_id:artifact,base_version:2,version:3,change_scope:"major",feedback:"Keep the cost"} } : {
  path:`/api/books/${bookId}/chapters/${chapterNo}/briefs`,body:{book_id:bookId,chapter_no:chapterNo,state_artifact_id:artifact,state_version:2,version:3,feedback:"Keep the cost"} };}
const decision={path:`/api/story-planning/runs/${run}/decision`,body:{step_id:`SR-${"e".repeat(32)}`,artifact_id:artifact,expected_version:3,action:"approve",operator:"Original editor",reason:"Verified story rules"}};
function serve(read:()=>Response=()=>Response.json({run:{pipeline_run_id:run},request:{book_id:book}})) {
  const transport=vi.fn((url: unknown,init: RequestInit)=>Promise.resolve(init.method==="POST" ? Response.json({saved:true}) : String(url)===decision.path.replace(/\/decision$/,"") ? read() : Response.json([])));
  vi.stubGlobal("fetch",transport);return transport;
}
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();sessionStorage.clear();});
test.each([[otherBook,null],[otherBook,3],[book,10001],[book,Number.MAX_SAFE_INTEGER]] as const)(
  "a foreign or unsupported planning command never posts from this Book: %s/%s",async(bookId,chapterNo)=>{
    const bytes=JSON.stringify(command(bookId,chapterNo));sessionStorage.setItem(key,bytes);const transport=serve();render(<StoryPlanning bookId={book} approvedBible />);
    await act(async()=>{});const retry=screen.queryByRole("button",{name:"Retry the same request"});if(retry)fireEvent.click(retry);await act(async()=>{});
    expect(transport.mock.calls.filter(([,init])=>init.method==="POST").map(([url,init])=>({path:url,body:JSON.parse(String(init.body))}))).toEqual([]);
    expect(screen.queryByRole("button",{name:"Retry the same request"})).toBeNull();expect(screen.getByText("Saved request is unreadable. Check the Book history before clearing it.")).toBeTruthy();expect(sessionStorage.getItem(key)).toBe(bytes);
    fireEvent.click(screen.getByRole("button",{name:"I checked the history"}));expect(sessionStorage.getItem(key)).toBeNull();
  });
test.each([null,1,3,10000])("a saved own-Book planning command preserves chapter %s and all sources",async chapterNo=>{
  const exact=command(book,chapterNo);sessionStorage.setItem(key,JSON.stringify(exact));const transport=serve();render(<StoryPlanning bookId={book} approvedBible />);
  expect(screen.getByLabelText("Chapter number")).toHaveProperty("value","1");fireEvent.click(screen.getByRole("button",{name:"Retry the same request"}));await waitFor(()=>expect(sessionStorage.getItem(key)).toBeNull());
  const posts=transport.mock.calls.filter(([,init])=>init.method==="POST");expect(posts).toHaveLength(1);expect(posts[0][0]).toBe(exact.path);expect(JSON.parse(String(posts[0][1].body))).toEqual(exact.body);
  expect(transport.mock.calls.some(([url])=>String(url).endsWith("/context"))).toBe(false);
});
test.each(["foreign Book","wrong run"])("a saved opaque decision must verify its original %s before any POST",async fault=>{
  const bytes=JSON.stringify(decision);sessionStorage.setItem(key,bytes);const transport=serve(()=>Response.json({run:{pipeline_run_id:fault==="wrong run"?`PR-${"f".repeat(32)}`:run},request:{book_id:fault==="foreign Book"?otherBook:book}}));render(<StoryPlanning bookId={book} approvedBible />);
  fireEvent.click(screen.getByRole("button",{name:"Retry the same request"}));await act(async()=>{});
  expect(transport.mock.calls.filter(([,init])=>init.method==="POST").map(([url,init])=>({path:url,body:JSON.parse(String(init.body))}))).toEqual([]);
  expect(await screen.findByText("Saved planning decision does not match this Book and run. Check the original Book history before retrying.")).toBeTruthy();expect(sessionStorage.getItem(key)).toBe(bytes);
  fireEvent.click(screen.getByRole("button",{name:"I checked the history"}));expect(sessionStorage.getItem(key)).toBeNull();
});
test("an opaque same-Book decision is verified then replayed with its original signature and target",async()=>{
  sessionStorage.setItem(key,JSON.stringify(decision));const transport=serve();render(<StoryPlanning bookId={book} approvedBible />);fireEvent.click(screen.getByRole("button",{name:"Retry the same request"}));await waitFor(()=>expect(sessionStorage.getItem(key)).toBeNull());
  const calls=transport.mock.calls.filter(([url])=>String(url).startsWith("/api/story-planning/runs/"));expect(calls.map(([url,init])=>[url,new Request("http://localhost"+String(url),init).method])).toEqual([[decision.path.replace(/\/decision$/,""),"GET"],[decision.path,"POST"]]);expect(JSON.parse(String(calls[1][1].body))).toEqual(decision.body);
});
test("unavailable opaque-decision ownership read preserves intent and retries only after explicit recovery",async()=>{
  let unavailable=true;const bytes=JSON.stringify(decision);sessionStorage.setItem(key,bytes);const transport=serve(()=>unavailable?Response.json({detail:"Ownership temporarily unreadable"},{status:503}):Response.json({run:{pipeline_run_id:run},request:{book_id:book}}));render(<StoryPlanning bookId={book} approvedBible />);fireEvent.click(screen.getByRole("button",{name:"Retry the same request"}));await act(async()=>{});
  expect(transport.mock.calls.filter(([,init])=>init.method==="POST")).toHaveLength(0);expect(await screen.findByText("Ownership temporarily unreadable")).toBeTruthy();expect(sessionStorage.getItem(key)).toBe(bytes);
  unavailable=false;fireEvent.click(screen.getByRole("button",{name:"Retry the same request"}));await waitFor(()=>expect(sessionStorage.getItem(key)).toBeNull());const calls=transport.mock.calls.filter(([url])=>String(url).startsWith("/api/story-planning/runs/"));expect(calls.map(([url,init])=>new Request("http://localhost"+String(url),init).method)).toEqual(["GET","GET","POST"]);expect(JSON.parse(String(calls[2][1].body))).toEqual(decision.body);
});
