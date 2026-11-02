// Page-wide keyboard shortcuts (ui.md §4.1, §7). Single-character keys are ignored while the user
// types in a field, so `/` can still be typed into a query; Escape always reaches its handler.
import { useEffect, useRef } from "react";

export type ShortcutMap = Partial<Record<string, (event: KeyboardEvent) => void>>;

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT";
}

export function useShortcuts(shortcuts: ShortcutMap): void {
  // the latest handlers, without re-binding the listener on every render
  const current = useRef(shortcuts);
  useEffect(() => {
    current.current = shortcuts;
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      const handler = current.current[event.key];
      if (!handler) return;
      if (event.key !== "Escape" && isTyping(event.target)) return;
      handler(event);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
