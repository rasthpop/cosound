// Inline play/pause for a result row (ui.md §4.2). Only rendered with a playable URL. "One track
// at a time" is the container's job: it passes `playing` for the one track it is playing.
import { Pause, Play } from "lucide-react";
import { useEffect, useRef } from "react";

import { ICON } from "@/theme/tokens/semantic";

import { Button } from "../ui/button";

export interface MiniPlayerProps {
  /** A playable URL (the container resolves `preview_url` with useMediaUrl). */
  src: string;
  /** Track title, for the button's accessible name. */
  title: string;
  playing: boolean;
  /** Toggle request: `true` to play, `false` to pause. */
  onPlayingChange: (playing: boolean) => void;
}

export function MiniPlayer({ src, title, playing, onPlayingChange }: MiniPlayerProps) {
  const audio = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    const el = audio.current;
    if (!el) return;
    if (playing) {
      // play() rejects when the browser blocks autoplay or the clip fails; report it as paused
      void Promise.resolve(el.play?.()).catch(() => onPlayingChange(false));
    } else {
      el.pause?.();
    }
  }, [playing, onPlayingChange]);

  return (
    <>
      <Button
        size="icon-sm"
        variant="ghost"
        aria-label={playing ? `Pause ${title}` : `Play ${title}`}
        aria-pressed={playing}
        onClick={() => onPlayingChange(!playing)}
      >
        {playing ? <Pause aria-hidden="true" {...ICON} /> : <Play aria-hidden="true" {...ICON} />}
      </Button>
      <audio ref={audio} src={src} preload="none" onEnded={() => onPlayingChange(false)} />
    </>
  );
}
