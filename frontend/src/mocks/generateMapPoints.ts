// Synthetic map points for performance work (e.g. 10k points). Deterministic for a seed;
// generated at runtime, never committed. Fictional ids and titles only.
import type { MapPoint } from "../api/types";

const GENRES = ["Electronic", "Experimental", "Folk", "Hip-Hop", "Instrumental", "International", "Pop", "Rock"];

/** Small deterministic PRNG (mulberry32). */
function random(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** `count` points clustered by genre inside [-1, 1]², sorted by track id like the API. */
export function generateMapPoints(count: number, seed = 42): MapPoint[] {
  const next = random(seed);
  const centers = GENRES.map((_, i) => {
    const angle = (2 * Math.PI * i) / GENRES.length;
    return [0.6 * Math.cos(angle), 0.6 * Math.sin(angle)] as const;
  });
  const points: MapPoint[] = [];
  for (let i = 0; i < count; i++) {
    const g = Math.floor(next() * GENRES.length);
    const [cx, cy] = centers[g] ?? [0, 0];
    const spread = () => (next() + next() + next() - 1.5) * 0.25;
    const id = String(i + 1).padStart(6, "0");
    points.push({
      track_id: `trk_synthetic_${id}`,
      x: Math.max(-1, Math.min(1, cx + spread())),
      y: Math.max(-1, Math.min(1, cy + spread())),
      title: `Synthetic Track ${id}`,
      artist: `Synthetic Artist ${(i % 97) + 1}`,
      genre: GENRES[g] ?? null,
      style: null,
      source_url: null,
      has_audio: true,
    });
  }
  return points;
}
