import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const server = setupServer(
  http.get("/backend/api/auth/me", () =>
    HttpResponse.json(
      { error: { code: "unauthorized", message: "Unauthenticated" } },
      { status: 401 },
    ),
  ),
);
