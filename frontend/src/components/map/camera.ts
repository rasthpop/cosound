// Camera transitions (ui.md §4.3: 600 ms ease-out fly-to; instant under reduced motion). deck.gl
// takes an easing function, so the token's ease-out curve is expressed as one here.
import type { MotionSet } from "@/theme/tokens/types";

export interface CameraTransition {
  transitionDuration: number;
  transitionEasing: (t: number) => number;
}

/** Cubic ease-out: fast start, gentle stop (the motion token's "out" curve). */
export const easeOut = (t: number): number => 1 - (1 - t) ** 3;

export function cameraTransition(motion: MotionSet): CameraTransition {
  return { transitionDuration: motion.duration.camera, transitionEasing: easeOut };
}
