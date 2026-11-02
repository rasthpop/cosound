// One story per state view (ui.md §6), fed from the contract fixtures.
import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";

import { fixture } from "@/mocks/fixtures";

import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { NoConfidentMatch } from "./NoConfidentMatch";
import { OfflineState } from "./OfflineState";
import { StatusPill } from "./StatusPill";

const Panel = ({ children }: { children: ReactNode }) => (
  <main className="min-h-dvh bg-surface-canvas p-3 text-fg">
    <div className="w-47.5 rounded-lg border border-hairline bg-surface-panel backdrop-blur-panel">{children}</div>
  </main>
);

const meta = { title: "States", parameters: { layout: "fullscreen" } } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const noMatch = fixture("search_no_confident_match");
const degraded = fixture("search_semantic_unavailable");

export const Empty: Story = {
  render: () => (
    <Panel>
      <EmptyState query={fixture("search_empty").interpreted_query.original_query} onEditQuery={() => {}} />
    </Panel>
  ),
};

export const NoConfidentMatchState: Story = {
  name: "No confident match",
  render: () => (
    <Panel>
      <NoConfidentMatch reasons={noMatch.no_match_reasons} onEditQuery={() => {}} />
    </Panel>
  ),
};

export const Error: Story = {
  render: () => (
    <Panel>
      <ErrorState error={fixture("error_internal").error} onRetry={() => {}} />
    </Panel>
  ),
};

export const Offline: Story = {
  render: () => (
    <Panel>
      <OfflineState query="something chill with a flute" onRetry={() => {}} />
    </Panel>
  ),
};

export const PillSemanticDegraded: Story = {
  name: "Status pill: semantic off",
  render: () => (
    <Panel>
      <StatusPill capabilities={degraded.capabilities} />
    </Panel>
  ),
};

export const PillMapDown: Story = {
  name: "Status pill: map down + offline",
  render: () => (
    <Panel>
      <StatusPill capabilities={{ semantic: "available", map: "unavailable" }} offline onRetry={() => {}} />
    </Panel>
  ),
};

export const PillHidden: Story = {
  name: "Status pill: nothing degraded (renders nothing)",
  render: () => (
    <Panel>
      <StatusPill capabilities={fixture("search_ok").capabilities} />
      <p className="p-2 text-meta text-muted">Nothing is degraded, so no pill.</p>
    </Panel>
  ),
};

export const LightTheme: Story = {
  globals: { theme: "light" },
  render: () => (
    <Panel>
      <NoConfidentMatch reasons={noMatch.no_match_reasons} onEditQuery={() => {}} />
      <StatusPill capabilities={degraded.capabilities} offline onRetry={() => {}} />
    </Panel>
  ),
};
