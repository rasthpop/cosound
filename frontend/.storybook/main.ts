// Storybook workbench (ADR-0003): every view state is a story, built against the contract mocks.
import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-a11y", "@storybook/addon-themes", "@storybook/addon-vitest", "msw-storybook-addon"],
  framework: { name: "@storybook/react-vite", options: {} },
  // public/ holds MSW's mockServiceWorker.js for msw-storybook-addon
  staticDirs: ["../public"],
};

export default config;
