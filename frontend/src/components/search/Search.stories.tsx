// Search bar, chips and clarification in every state the plan lists (U02.T02), from fixtures.
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState, type ReactNode } from "react";
import { expect, userEvent, within } from "storybook/test";

import { fixture } from "@/mocks/fixtures";

import { ClarificationPrompt } from "./ClarificationPrompt";
import { QueryChips } from "./QueryChips";
import { SearchBar, type SearchBarProps } from "./SearchBar";

const EXAMPLES = ["something chill with a flute", "dark ambient without vocals", "upbeat folk from the 2000s"];

const Stage = ({ children }: { children: ReactNode }) => (
  <main className="flex min-h-dvh flex-col items-center gap-1 bg-surface-canvas px-2 pt-3 text-fg">{children}</main>
);

function Bar(props: Partial<SearchBarProps> & { initial?: string }) {
  const [value, setValue] = useState(props.initial ?? "");
  return <SearchBar examples={EXAMPLES} onQuerySubmit={() => {}} {...props} value={value} onValueChange={setValue} />;
}

const meta = { title: "Search" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Idle: Story = { render: () => <Stage><Bar /></Stage> };

export const FocusedWithExamples: Story = {
  render: () => (
    <Stage>
      <Bar />
    </Stage>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole("textbox"));
    await expect(canvas.getByText("something chill with a flute")).toBeVisible();
  },
};

export const LoadingStale: Story = {
  name: "Loading (previous results stale)",
  render: () => (
    <Stage>
      <Bar initial="something chill with a flute" loading stale />
    </Stage>
  ),
};

export const RefineAvailable: Story = {
  render: () => (
    <Stage>
      <Bar initial="more acoustic" canRefine onRefineSubmit={() => {}} />
    </Stage>
  ),
};

const ok = fixture("search_ok");
const hard = fixture("search_constraint_unknown");
const fallback = fixture("search_llm_fallback");
const clarify = fixture("search_needs_clarification");

export const InterpretedSoft: Story = {
  name: "Interpreted: soft preferences",
  render: () => (
    <Stage>
      <Bar initial={ok.interpreted_query.original_query} />
      <QueryChips query={ok.interpreted_query} onAttributeFeedback={() => {}} />
    </Stage>
  ),
};

export const InterpretedHardAndNegative: Story = {
  name: "Interpreted: hard constraint + negative",
  render: () => (
    <Stage>
      <Bar initial={hard.interpreted_query.original_query} />
      <QueryChips query={hard.interpreted_query} onAttributeFeedback={() => {}} onEditQuery={() => {}} />
    </Stage>
  ),
};

export const LlmFallback: Story = {
  name: "LLM fallback note",
  render: () => (
    <Stage>
      <Bar initial={fallback.interpreted_query.original_query} />
      <QueryChips
        query={fallback.interpreted_query}
        interpreterFallback={fallback.capabilities.llm_interpreter === "fallback"}
        onAttributeFeedback={() => {}}
      />
    </Stage>
  ),
};

export const NeedsClarification: Story = {
  render: () => (
    <Stage>
      <Bar initial={clarify.interpreted_query.original_query} />
      <QueryChips query={clarify.interpreted_query} onAttributeFeedback={() => {}} />
      {clarify.clarification_question && <ClarificationPrompt question={clarify.clarification_question} onReply={() => {}} />}
    </Stage>
  ),
};

export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => (
    <Stage>
      <Bar initial={hard.interpreted_query.original_query} loading stale />
      <QueryChips query={hard.interpreted_query} onAttributeFeedback={() => {}} onEditQuery={() => {}} />
    </Stage>
  ),
};
