// One clip at a time across the results rows and the details drawer (ui.md §4.2, §4.4). The row
// players are controlled by the page (`playingId`); the drawer's is a native <audio controls>. So
// the rule is enforced at the document: when any <audio> starts, every other one pauses, and the
// page hears which one started (to clear a row's "playing" state when the drawer took over).
import { useEffect, useRef } from "react";

/** Marks the details drawer's player (set by AudioPlayer). */
export const DETAILS_PLAYER = "details";

export const isDetailsPlayer = (audio: HTMLAudioElement) => audio.dataset.player === DETAILS_PLAYER;

/** Pause every <audio> in `root` except `playing`. */
export function pauseOthers(playing: HTMLAudioElement, root: ParentNode = document): void {
  for (const audio of root.querySelectorAll("audio")) {
    if (audio !== playing && !audio.paused) audio.pause();
  }
}

export function useSinglePlayback(onPlay?: (audio: HTMLAudioElement) => void): void {
  const callback = useRef(onPlay);
  useEffect(() => {
    callback.current = onPlay;
  });
  useEffect(() => {
    // `play` does not bubble: listen in the capture phase
    const listener = (event: Event) => {
      if (!(event.target instanceof HTMLAudioElement)) return;
      pauseOthers(event.target);
      callback.current?.(event.target);
    };
    document.addEventListener("play", listener, true);
    return () => document.removeEventListener("play", listener, true);
  }, []);
}
