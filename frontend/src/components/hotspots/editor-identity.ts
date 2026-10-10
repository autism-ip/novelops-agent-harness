"use client";

import { useSyncExternalStore } from "react";

const KEY = "novelops.editor.name";
const EVENT = "novelops-editor-name";
let memoryOperator = "";

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}

function snapshot() {
  try { return sessionStorage.getItem(KEY) ?? ""; } catch { return memoryOperator; }
}

export function useEditorIdentity() {
  const operator = useSyncExternalStore(subscribe, snapshot, () => "");
  function update(value: string) {
    memoryOperator = value;
    try { sessionStorage.setItem(KEY, value); } catch { /* Keep this tab's editor name in memory. */ }
    window.dispatchEvent(new Event(EVENT));
  }
  return { operator, update };
}
