import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom không có crypto.randomUUID — polyfill tối giản cho use-session/use-cart
if (typeof globalThis.crypto?.randomUUID !== "function") {
  Object.defineProperty(globalThis.crypto, "randomUUID", {
    value: () =>
      "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
      }),
  });
}

// jsdom thiếu Pointer Capture API — Radix Select gọi hasPointerCapture/setPointerCapture
if (typeof Element !== "undefined" && !Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
}
afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
});
