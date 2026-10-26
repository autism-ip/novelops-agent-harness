import { createRef } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../src/components/ui/card";
import { Table, TableHeader, TableBody, TableFooter, TableRow, TableHead, TableCell, TableCaption } from "../src/components/ui/table";
import { DataTable, type Column } from "../src/components/data-table";

afterEach(cleanup);

test("a composed writing card keeps its accessible title, description, reading order, refs and action", () => {
  const card=createRef<HTMLDivElement>(),header=createRef<HTMLDivElement>(),title=createRef<HTMLDivElement>();
  const description=createRef<HTMLDivElement>(),content=createRef<HTMLDivElement>(),footer=createRef<HTMLDivElement>();
  const inspect=vi.fn();
  render(<Card ref={card} role="region" aria-labelledby="draft-title" aria-describedby="draft-description" className="writing-card" data-source="chapter-3">
    <CardHeader ref={header} className="writing-header">
      <CardTitle ref={title} id="draft-title" role="heading" aria-level={2} className="writing-title">Chapter 3 review</CardTitle>
      <CardDescription ref={description} id="draft-description" className="writing-description">Inspect this draft before deciding.</CardDescription>
    </CardHeader>
    <CardContent ref={content} className="writing-content"><p>The gate opens at dawn.</p></CardContent>
    <CardFooter ref={footer} className="writing-footer"><button onClick={inspect}>Inspect source</button></CardFooter>
  </Card>);
  const region=screen.getByRole("region",{name:"Chapter 3 review"});
  expect(card.current).toBe(region);expect(region.getAttribute("aria-describedby")).toBe(description.current?.id);
  expect(title.current).toBe(screen.getByRole("heading",{name:"Chapter 3 review",level:2}));
  expect(description.current?.textContent).toBe("Inspect this draft before deciding.");
  expect(content.current?.textContent).toBe("The gate opens at dawn.");expect(region.getAttribute("data-source")).toBe("chapter-3");
  expect(region.classList.contains("surface")).toBe(true);expect(region.classList.contains("writing-card")).toBe(true);
  for(const [ref,name] of [[header,"writing-header"],[title,"writing-title"],[description,"writing-description"],[content,"writing-content"],[footer,"writing-footer"]] as const)
    expect(ref.current?.classList.contains(name)).toBe(true);
  expect(header.current!.compareDocumentPosition(content.current!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(content.current!.compareDocumentPosition(footer.current!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  fireEvent.click(within(region).getByRole("button",{name:"Inspect source"}));expect(inspect).toHaveBeenCalledOnce();
});

test("the shared table preserves caption, column/row semantics, selected state, footer and refs", () => {
  const table=createRef<HTMLTableElement>(),header=createRef<HTMLTableSectionElement>(),body=createRef<HTMLTableSectionElement>(),footer=createRef<HTMLTableSectionElement>();
  const caption=createRef<HTMLTableCaptionElement>(),row=createRef<HTMLTableRowElement>(),head=createRef<HTMLTableCellElement>(),cell=createRef<HTMLTableCellElement>();
  const inspect=vi.fn();
  render(<Table ref={table} aria-label="Chapter versions" className="version-table" data-scope="chapter-3">
    <TableCaption ref={caption} className="version-caption">Every earlier version remains readable.</TableCaption>
    <TableHeader ref={header} className="version-header"><TableRow><TableHead ref={head} scope="col" className="version-head">Version</TableHead><TableHead scope="col">Status</TableHead></TableRow></TableHeader>
    <TableBody ref={body} className="version-body"><TableRow ref={row} className="selected-version" data-state="selected" onClick={inspect}><TableHead scope="row">v2</TableHead><TableCell ref={cell} className="version-cell">Review</TableCell></TableRow></TableBody>
    <TableFooter ref={footer} className="version-footer"><TableRow><TableCell colSpan={2}>1 stored version</TableCell></TableRow></TableFooter>
  </Table>);
  expect(table.current).toBe(screen.getByRole("table",{name:"Chapter versions"}));expect(table.current?.caption).toBe(caption.current);
  expect(caption.current?.textContent).toBe("Every earlier version remains readable.");expect(table.current?.tHead).toBe(header.current);expect(table.current?.tBodies[0]).toBe(body.current);expect(table.current?.tFoot).toBe(footer.current);
  expect(head.current).toBe(screen.getByRole("columnheader",{name:"Version"}));expect(screen.getByRole("rowheader",{name:"v2"}).getAttribute("scope")).toBe("row");
  expect(cell.current).toBe(screen.getByRole("cell",{name:"Review"}));expect(row.current?.dataset.state).toBe("selected");expect(table.current?.getAttribute("data-scope")).toBe("chapter-3");
  expect(footer.current?.textContent).toBe("1 stored version");expect(footer.current?.querySelector("td")?.colSpan).toBe(2);
  expect(table.current?.classList.contains("version-table")).toBe(true);expect(table.current?.parentElement?.classList.contains("overflow-auto")).toBe(true);
  for(const [ref,name] of [[caption,"version-caption"],[header,"version-header"],[body,"version-body"],[footer,"version-footer"],[head,"version-head"],[cell,"version-cell"]] as const)expect(ref.current?.classList.contains(name)).toBe(true);
  fireEvent.click(cell.current!);expect(inspect).toHaveBeenCalledOnce();
});

test.each([undefined,"No chapter versions yet. Generate a verified draft first."])("an actually empty table shows its supplied guidance: %s", emptyMessage => {
  render(<DataTable columns={[{key:"version",label:"Version"}]} data={[] as {version:number}[]} emptyMessage={emptyMessage} />);
  expect(screen.getByText(emptyMessage??"No data")).toBeTruthy();expect(screen.queryByRole("table")).toBeNull();
});

test("table values keep zero/false, leave missing values blank, and preserve domain identity in custom actions", () => {
  type Row={id:string;count:number;enabled:boolean;missing:null|undefined};const inspect=vi.fn();
  const columns:Column<Row>[]=[{key:"count",label:"Count"},{key:"enabled",label:"Enabled"},{key:"missing",label:"Optional source"},{key:"id",label:"Action",render:(_value,row)=><button onClick={()=>inspect(row.id)}>Open {row.id}</button>}];
  const {rerender}=render(<DataTable columns={columns} data={[{id:"CV-source",count:0,enabled:false,missing:null}]} />);
  const cells=within(screen.getAllByRole("row")[1]).getAllByRole("cell");expect(cells.map(c=>c.textContent)).toEqual(["0","false","","Open CV-source"]);
  fireEvent.click(screen.getByRole("button",{name:"Open CV-source"}));expect(inspect).toHaveBeenCalledExactlyOnceWith("CV-source");
  rerender(<DataTable columns={columns} data={[{id:"CV-next",count:1,enabled:true,missing:undefined}]} />);
  expect(within(screen.getAllByRole("row")[1]).getAllByRole("cell").map(c=>c.textContent)).toEqual(["1","true","","Open CV-next"]);
});
