import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fixture } from "@/mocks/fixtures";

import { NeighborList } from "./NeighborList";
import { RelatedTracks } from "./RelatedTracks";
import { TrackDetailsDrawer, type TrackDetailsDrawerProps } from "./TrackDetailsDrawer";

afterEach(cleanup);

function drawer(props: Partial<TrackDetailsDrawerProps> = {}) {
  const detail = fixture("track_detail");
  return render(<TrackDetailsDrawer open onClose={() => {}} status="ready" detail={detail} playUrl="blob:clip" {...props} />);
}

describe("TrackDetailsDrawer", () => {
  it("shows the facts, the player with license and FMA credit, and no FMA link without source_url", () => {
    drawer();
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Example Track 1" })).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Example Album (2012)");
    expect(dialog).toHaveTextContent("3:32");
    expect(dialog).toHaveTextContent("License: Example license");
    expect(dialog).toHaveTextContent("Free Music Archive");
    expect(within(dialog).queryByRole("link", { name: /Open on FMA/ })).toBeNull();
  });

  it("says there is no preview and renders nothing for absent fields", () => {
    drawer({ detail: fixture("track_detail_no_audio"), playUrl: null });
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("No audio preview available.");
    expect(dialog).not.toHaveTextContent(/Release|Year|Duration|License/);
  });

  it("opens FMA safely when there is a source_url", () => {
    drawer({ detail: { ...fixture("track_detail"), source_url: "https://freemusicarchive.org/t/1" } });
    expect(screen.getByRole("link", { name: /Open on FMA/ })).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("closing with ✕ or Esc calls onClose, and the container can restore focus", async () => {
    const onClose = vi.fn();
    const onCloseAutoFocus = vi.fn((e: Event) => e.preventDefault());
    const { rerender } = drawer({ onClose, onCloseAutoFocus });
    await userEvent.click(screen.getByRole("button", { name: "Close details" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(2);
    rerender(<TrackDetailsDrawer open={false} onClose={onClose} onCloseAutoFocus={onCloseAutoFocus} status="ready" detail={fixture("track_detail")} playUrl={null} />);
    // Radix moves focus after unmount, asynchronously
    await waitFor(() => expect(onCloseAutoFocus).toHaveBeenCalled());
  });

  it("loops Tab inside the non-modal desktop drawer", async () => {
    drawer();
    const close = screen.getByRole("button", { name: "Close details" });
    close.focus(); // the last focusable element
    await userEvent.tab();
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true);
  });

  it("explains not-found without technical detail", () => {
    drawer({ status: "error", detail: null, error: { code: "track_not_found" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Track not found");
    expect(screen.getByRole("alert")).not.toHaveTextContent("track_not_found");
  });
});

describe("NeighborList and RelatedTracks", () => {
  it("labels neighbors by metric, shows the fallback reason and selects a neighbor", async () => {
    const onTrackSelect = vi.fn();
    render(<NeighborList neighbors={fixture("neighbors_no_audio")} onTrackSelect={onTrackSelect} />);
    expect(screen.getByRole("heading", { name: "Related in the catalog" })).toBeInTheDocument();
    expect(screen.getByText(/no audio analysis/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Example Track 5/ }));
    expect(onTrackSelect).toHaveBeenCalledWith("trk_example_5");
  });

  it("sound neighbors say so, and related tracks group by relationship", () => {
    render(<NeighborList neighbors={fixture("neighbors")} onTrackSelect={() => {}} />);
    expect(screen.getByRole("heading", { name: "Nearby in sound" })).toBeInTheDocument();
    render(<RelatedTracks related={fixture("track_detail").related_tracks} onTrackSelect={() => {}} />);
    expect(screen.getByRole("heading", { name: "Same artist" })).toBeInTheDocument();
  });
});
