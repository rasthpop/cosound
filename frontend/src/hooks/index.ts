// The functional/visual seam: containers (src/pages/) import hooks and their types from here.
// API data types come from "@/api/types". See README.md for the contract of each hook.
export type { RequestStatus } from "./status";

export { useMusicSearch } from "./useMusicSearch";
export type { MusicSearch, SearchCallOptions, UseMusicSearchOptions } from "./useMusicSearch";

export { PLATE_KEY, useTrackFeedback } from "./useTrackFeedback";
export type {
  FeedbackCallOptions,
  FeedbackInput,
  FeedbackState,
  TrackFeedback,
  UseTrackFeedbackOptions,
} from "./useTrackFeedback";

export { useTrackDetails } from "./useTrackDetails";
export type { TrackDetailsState, UseTrackDetailsOptions } from "./useTrackDetails";

export { useMusicMap } from "./useMusicMap";
export type { MapAvailability, MusicMap, UseMusicMapOptions } from "./useMusicMap";

export { useSystemStatus } from "./useSystemStatus";
export type { SystemStatus, UseSystemStatusOptions } from "./useSystemStatus";

export { useMediaUrl } from "./useMediaUrl";
export type { UseMediaUrlOptions } from "./useMediaUrl";
