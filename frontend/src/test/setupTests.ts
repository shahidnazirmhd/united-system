import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL doesn't auto-unmount between tests under Vitest the way some other
// runners wire it up automatically — without this, a component rendered in
// one test can still be attached to the DOM when the next test runs.
afterEach(() => {
  cleanup();
});

// jsdom (the environment vitest.config.ts uses) does not implement
// `window.matchMedia` at all — ThemeProvider and useMediaQuery both call it
// directly, so any test that renders them would throw
// "not implemented" without this stub.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  });
}
