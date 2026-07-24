import { afterEach, describe, expect, it, vi } from "vitest";
import { getCurrentUser, loginUser } from "./client";

describe("authentication API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("includes credentials and unwraps the current user", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ user: { id: "user_1", name: "Hiba", email: "hiba@example.com" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCurrentUser()).resolves.toMatchObject({ id: "user_1", email: "hiba@example.com" });
    expect(fetchMock).toHaveBeenCalledWith("/backend/api/auth/me", expect.objectContaining({ credentials: "include" }));
  });

  it("parses the backend nested error envelope", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      message: "Email atau kata sandi salah",
      error: { code: "unauthorized", message: "Email atau kata sandi salah" },
    }), { status: 401, headers: { "Content-Type": "application/json" } })));

    await expect(loginUser({ email: "hiba@example.com", password: "wrong-password" })).rejects.toMatchObject({
      status: 401,
      code: "unauthorized",
      message: "Email atau kata sandi salah",
    });
  });
});
