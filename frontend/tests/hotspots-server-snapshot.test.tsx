import { afterEach, expect, test, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { HotspotsWorkbench } from "../src/components/hotspots/workbench";

const key = "novelops.hotspots.pending";
const original = JSON.stringify({ path: "/api/hotspots/manual", body: {
  request_key: "private-tab-command", title: "Private unpublished idea", url: "", category: "fiction" } });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

test.each([false, true])("server prerender ignores tab-only recovery state even when storage access is denied=%s", denied => {
  sessionStorage.setItem(key, original);
  const get = vi.spyOn(Storage.prototype, "getItem");
  if (denied) get.mockImplementation(() => { throw new DOMException("Storage access denied", "SecurityError"); });
  const transport = vi.fn(() => { throw new Error("Server prerender must not issue browser workflow requests"); });
  vi.stubGlobal("fetch", transport);
  const html = renderToString(<HotspotsWorkbench />);
  const document = new DOMParser().parseFromString(html, "text/html");
  expect(document.querySelector("h1")?.textContent).toBe("Hotspots");
  expect(html).toContain("Loading hotspots");
  for (const value of ["private-tab-command", "Private unpublished idea", "Retry same request", "Saved request is unreadable", "Cannot access saved requests"])
    expect(html).not.toContain(value);
  expect(get).not.toHaveBeenCalled();
  expect(transport).not.toHaveBeenCalled();
  get.mockRestore();
  expect(sessionStorage.getItem(key)).toBe(original);
});
