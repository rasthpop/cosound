// Full-width preview player for the details drawer (ui.md §4.4): native <audio> controls, the
// track's own license and the FMA credit next to it. Without a playable URL it says so.
import { formatDuration } from "../format/text";

export interface AudioPlayerProps {
  /** Playable URL (the container resolves `preview_url`); `null` = no preview. */
  src: string | null;
  title: string;
  /** `TrackDetail.audio.license`; shown only when recorded. */
  license: string | null;
  /** Length of the preview clip (`TrackDetail.audio.duration_seconds`). */
  clipSeconds: number | null;
}

export function AudioPlayer({ src, title, license, clipSeconds }: AudioPlayerProps) {
  if (!src) return <p className="text-meta text-muted">No audio preview available.</p>;
  const clip = formatDuration(clipSeconds);
  return (
    <figure className="flex flex-col gap-0.5">
      <audio controls preload="none" src={src} aria-label={`Preview of ${title}`} className="w-full" />
      <figcaption className="flex flex-col text-meta text-muted">
        {clip && <span>{clip} preview</span>}
        {license && <span>License: {license}</span>}
        <span>Audio and metadata from the Free Music Archive (FMA).</span>
      </figcaption>
    </figure>
  );
}
