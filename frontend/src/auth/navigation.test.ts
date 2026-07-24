import { afterEach, describe, expect, it } from "vitest";
import { safeNext } from "./navigation";

describe("safeNext", () => {
  afterEach(() => window.history.replaceState(null, "", "/"));

  it("preserves internal paths with query and hash", () => {
    expect(safeNext("/simulation/sim_1?step=report#section")).toBe("/simulation/sim_1?step=report#section");
  });

  it("rejects external and protocol-relative destinations", () => {
    expect(safeNext("https://evil.example/path")).toBe("/dashboard");
    expect(safeNext("//evil.example/path")).toBe("/dashboard");
  });
});
