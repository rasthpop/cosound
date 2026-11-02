import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fixture } from "@/mocks/fixtures";

import { ClarificationPrompt } from "./ClarificationPrompt";
import { QueryChips } from "./QueryChips";
import { SearchBar, type SearchBarProps } from "./SearchBar";

afterEach(cleanup);

function Bar(props: Partial<SearchBarProps>) {
  const [value, setValue] = useState("");
  return <SearchBar onQuerySubmit={() => {}} {...props} value={value} onValueChange={setValue} />;
}

describe("SearchBar", () => {
  it("submits the trimmed text on Enter and ignores blank input", async () => {
    const onQuerySubmit = vi.fn();
    render(<Bar onQuerySubmit={onQuerySubmit} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "   {Enter}");
    expect(onQuerySubmit).not.toHaveBeenCalled();
    await userEvent.type(input, "  chill flute {Enter}");
    expect(onQuerySubmit).toHaveBeenCalledWith("chill flute");
  });

  it("shows examples only while empty and focused, and an example submits", async () => {
    const onQuerySubmit = vi.fn();
    render(<Bar onQuerySubmit={onQuerySubmit} examples={["dark ambient"]} />);
    expect(screen.queryByText("dark ambient")).toBeNull();
    await userEvent.click(screen.getByRole("textbox"));
    await userEvent.click(screen.getByRole("button", { name: "dark ambient" }));
    expect(onQuerySubmit).toHaveBeenCalledWith("dark ambient");
  });

  it("Esc blurs the input", async () => {
    render(<Bar />);
    const input = screen.getByRole("textbox");
    await userEvent.click(input);
    await userEvent.keyboard("{Escape}");
    expect(input).not.toHaveFocus();
  });

  it("refine sends the text as a refinement only when switched on", async () => {
    const onQuerySubmit = vi.fn();
    const onRefineSubmit = vi.fn();
    render(<Bar canRefine onQuerySubmit={onQuerySubmit} onRefineSubmit={onRefineSubmit} />);
    await userEvent.type(screen.getByRole("textbox"), "more acoustic{Enter}");
    expect(onQuerySubmit).toHaveBeenCalledWith("more acoustic");
    await userEvent.click(screen.getByRole("button", { name: "Refine the current results" }));
    await userEvent.type(screen.getByRole("textbox"), "{Enter}");
    expect(onRefineSubmit).toHaveBeenCalledWith("more acoustic");
  });

  it("shows progress while loading", () => {
    render(<Bar loading stale />);
    expect(screen.getByRole("progressbar", { name: "Searching" })).toBeInTheDocument();
    expect(screen.getByRole("search")).toHaveAttribute("aria-busy", "true");
  });
});

describe("QueryChips", () => {
  it("soft chips emit typed attribute feedback", async () => {
    const onAttributeFeedback = vi.fn();
    render(<QueryChips query={fixture("search_ok").interpreted_query} onAttributeFeedback={onAttributeFeedback} />);
    await userEvent.click(screen.getByRole("button", { name: "flute: adjust" }));
    await userEvent.click(screen.getByRole("button", { name: "More of this" }));
    expect(onAttributeFeedback).toHaveBeenLastCalledWith({ eventType: "MORE_OF_ATTRIBUTE", attribute: "instrument", value: "flute" });
    await userEvent.click(screen.getByRole("button", { name: "chill: adjust" }));
    await userEvent.click(screen.getByRole("button", { name: "Less of this" }));
    expect(onAttributeFeedback).toHaveBeenLastCalledWith({ eventType: "LESS_OF_ATTRIBUTE", attribute: "mood", value: "chill" });
  });

  it("hard and negative chips are read-only and emit no feedback", async () => {
    const onAttributeFeedback = vi.fn();
    const onEditQuery = vi.fn();
    render(<QueryChips query={fixture("search_constraint_unknown").interpreted_query} onAttributeFeedback={onAttributeFeedback} onEditQuery={onEditQuery} />);
    const hard = screen.getByText("No vocals");
    const negative = screen.getByText("electronic");
    expect(hard.closest("button")).toBeNull();
    expect(negative.closest("button")).toBeNull();
    expect(negative).toHaveClass("line-through");
    await userEvent.click(hard);
    await userEvent.click(negative);
    expect(onAttributeFeedback).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Edit your search" }));
    expect(onEditQuery).toHaveBeenCalledOnce();
  });

  it("notes the LLM fallback and shows uncertainties as text", () => {
    const query = { ...fixture("search_needs_clarification").interpreted_query };
    render(<QueryChips query={query} interpreterFallback onAttributeFeedback={() => {}} />);
    expect(screen.getByText("vocals are both excluded and requested")).toBeInTheDocument();
    expect(screen.getByText(/language model didn't answer/)).toBeInTheDocument();
  });
});

describe("ClarificationPrompt", () => {
  it("shows the question and emits the reply", async () => {
    const onReply = vi.fn();
    render(<ClarificationPrompt question="Should the music have vocals or not?" onReply={onReply} />);
    expect(screen.getByText("Should the music have vocals or not?")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox"), "no vocals{Enter}");
    expect(onReply).toHaveBeenCalledWith("no vocals");
  });
});
