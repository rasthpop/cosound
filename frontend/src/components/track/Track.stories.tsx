// The details drawer in every state U02.T05 lists, from the contract fixtures.
import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";

import { fixture } from "@/mocks/fixtures";

import { FeedbackActions } from "../feedback/FeedbackActions";
import { NeighborList } from "./NeighborList";
import { RelatedTracks } from "./RelatedTracks";
import { TrackDetailsDrawer, type TrackDetailsDrawerProps } from "./TrackDetailsDrawer";

const result = fixture("search_ok").results[0];
const instruments = fixture("search_ok").interpreted_query.instrument_preferences.map((p) => p.value);

const Stage = ({ children }: { children: ReactNode }) => <main className="min-h-dvh bg-surface-canvas text-fg">{children}</main>;

function Drawer(props: Partial<TrackDetailsDrawerProps> & { neighbors?: "audio" | "catalog" | "loading" }) {
  const detail = props.detail === undefined ? fixture("track_detail") : props.detail;
  const neighbors = props.neighbors === "loading" ? null : fixture(props.neighbors === "catalog" ? "neighbors_no_audio" : "neighbors");
  return (
    <Stage>
      <TrackDetailsDrawer
        open
        onClose={() => {}}
        status="ready"
        detail={detail}
        playUrl={detail?.preview_url ? "data:audio/mpeg;base64," : null}
        actions={detail && <FeedbackActions trackId={detail.track_id} title={detail.title} instruments={instruments} layout="labels" onFeedback={() => {}} />}
        related={
          detail && (
            <>
              <NeighborList neighbors={neighbors} onTrackSelect={() => {}} />
              <RelatedTracks related={detail.related_tracks} onTrackSelect={() => {}} />
            </>
          )
        }
        {...props}
      />
    </Stage>
  );
}

const meta = { title: "Track details", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Detail: Story = {
  render: () => <Drawer description={result?.description ?? null} matchReasons={result?.match_reasons ?? []} />,
};
export const NoAudio: Story = {
  name: "No audio (catalog-fallback neighbors)",
  render: () => <Drawer detail={fixture("track_detail_no_audio")} neighbors="catalog" />,
};
export const NeighborsLoading: Story = { render: () => <Drawer neighbors="loading" /> };
export const Loading: Story = { render: () => <Drawer status="loading" detail={null} /> };
export const NotFound: Story = {
  render: () => <Drawer status="error" detail={null} error={fixture("error_track_not_found").error} />,
};
export const MobileSheet: Story = {
  globals: { viewport: { value: "mobile2", isRotated: false } },
  render: () => <Drawer variant="mobile" />,
};
export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => <Drawer description={result?.description ?? null} matchReasons={result?.match_reasons ?? []} />,
};
