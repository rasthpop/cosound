import "@testing-library/jest-dom/vitest";

import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "../src/mocks/server";

// jsdom lacks ResizeObserver, which Radix primitives (ScrollArea, Popover) use. A no-op stand-in
// is enough for unit tests; story tests run in a real browser with the real one.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// Any request without a handler fails the test: hooks and views never reach a real backend.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
