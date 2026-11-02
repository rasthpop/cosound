import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fixture } from "@/mocks/fixtures";

import { ChangeStrip } from "./ChangeStrip";
import { FeedbackActions } from "./FeedbackActions";

afterEach(cleanup);

const base = { trackId: "trk_example_1", title: "Example Track 1" };

describe("FeedbackActions", () => {
  it.each([
    ["More like this: Example Track 1", "MORE_LIKE_THIS"],
    ["Less like this: Example Track 1", "LESS_LIKE_THIS"],
    ["Not relevant: Example Track 1", "NOT_RELEVANT"],
  ] as const)("%s emits %s with the track id", async (name, eventType) => {
    const onFeedback = vi.fn();
    render(<FeedbackActions {...base} onFeedback={onFeedback} />);
    await userEvent.click(screen.getByRole("button", { name }));
    expect(onFeedback).toHaveBeenCalledWith({ trackId: "trk_example_1", eventType });
  });

  it("wrong instrument emits WRONG_INSTRUMENT with the picked instrument", async () => {
    const onFeedback = vi.fn();
    render(<FeedbackActions {...base} instruments={["flute", "piano"]} onFeedback={onFeedback} />);
    await userEvent.click(screen.getByRole("button", { name: "Wrong instrument in Example Track 1…" }));
    await userEvent.click(screen.getByRole("button", { name: "piano" }));
    expect(onFeedback).toHaveBeenCalledWith({ trackId: "trk_example_1", eventType: "WRONG_INSTRUMENT", attribute: "instrument", value: "piano" });
  });

  it("hides the instrument picker when the query names no instrument", () => {
    render(<FeedbackActions {...base} instruments={[]} onFeedback={() => {}} />);
    expect(screen.queryByRole("button", { name: /Wrong instrument/ })).toBeNull();
  });

  it("disables gestures while pending and reports rejected and error states", () => {
    const { rerender } = render(<FeedbackActions {...base} status="pending" lastEvent="NOT_RELEVANT" onFeedback={() => {}} />);
    expect(screen.getByRole("button", { name: "Not relevant: Example Track 1" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Sending…");
    const reason = fixture("feedback_rejected").reason ?? "";
    rerender(<FeedbackActions {...base} status="rejected" message={reason} onFeedback={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent(`Not applied: ${reason}`);
    rerender(<FeedbackActions {...base} status="error" message="That track is no longer in the results." onFeedback={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't send: That track is no longer in the results.");
  });
});

describe("ChangeStrip", () => {
  it("renders feedback_refined's change summary with the original query, and dismisses", async () => {
    const refined = fixture("feedback_refined");
    const onDismiss = vi.fn();
    render(<ChangeStrip changeSummary={refined.change_summary} originalQuery="Something chill with a flute" onDismiss={onDismiss} />);
    for (const change of refined.change_summary) expect(screen.getByText(change)).toBeInTheDocument();
    expect(screen.getByText("Refined “Something chill with a flute”")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /undo/i })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Dismiss what changed" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("renders nothing without changes", () => {
    const { container } = render(<ChangeStrip changeSummary={[]} originalQuery="x" onDismiss={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
