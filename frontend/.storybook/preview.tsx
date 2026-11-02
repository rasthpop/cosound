// Global story setup: token CSS, a theme toolbar that sets `data-theme` on <html> (the same switch
// the app's ThemeProvider makes), MSW for container stories, and axe on every story.
import { withThemeByDataAttribute } from "@storybook/addon-themes";
import type { Decorator, Preview } from "@storybook/react-vite";
import { mswLoader } from "msw-storybook-addon/csf3";

import { TooltipProvider } from "../src/components/ui/tooltip";
import "../src/theme/global.css";
import { ThemeProvider } from "../src/theme/ThemeProvider";
import { themes } from "../src/theme/tokens/semantic";
import type { ThemeName } from "../src/theme/tokens/types";

/** Keeps the ThemeProvider (useTheme, motion, tokens) in step with the toolbar's theme. */
const withThemeProvider: Decorator = (Story, context) => {
  const chosen = context.globals.theme as string | undefined;
  // the toolbar global can be "" or unset; anything that is not a theme name means the default
  const theme: ThemeName = chosen && chosen in themes ? (chosen as ThemeName) : "dark";
  return (
    <ThemeProvider key={theme} defaultPreference={theme} storageKey={null}>
      <TooltipProvider>
        <Story />
      </TooltipProvider>
    </ThemeProvider>
  );
};

const preview: Preview = {
  decorators: [
    withThemeProvider,
    withThemeByDataAttribute({
      themes: { dark: "dark", light: "light" },
      defaultTheme: "dark",
      attributeName: "data-theme",
    }),
  ],
  // container stories set `parameters.msw.handlers` from src/mocks (handlersFor(scenario))
  loaders: [mswLoader()],
  parameters: {
    // axe violations fail the story's test (npm run test-storybook)
    a11y: { test: "error" },
    layout: "fullscreen",
    controls: { expanded: true },
  },
};

export default preview;
