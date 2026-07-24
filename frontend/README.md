# RekaKebijakan

Landing page prototype for RekaKebijakan, a public policy early-stage simulation platform for GEMASTIK 2026.

## Running the project

```bash
bun install
bun run dev
```

To create a production build:

```bash
bun run build
bun run preview
```

The frontend uses `VITE_API_URL=/backend` by default. During development, Vite proxies that path to the FastAPI service at `http://localhost:5001`; the production Nginx configuration keeps the same `/backend` path. This same-origin path allows the browser to send the authentication cookie on all API requests. Copy `.env.example` to `.env` only when you need to override this path or force local demo behavior.

Authentication uses `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, and `GET /api/auth/me`. Dashboard, project, report, and simulation routes require an authenticated cookie session. Local workspace and workflow prototype data are namespaced by the authenticated user ID.

Public routes are `/`, `/login`, and `/register`. Registration requires a name, email, password of at least 6 characters, and matching password confirmation.

IDs beginning with `demo-` always use local demonstration data and timers. Setting `VITE_DEMO_MODE=true` forces the same local workflow mode for all IDs. The pilot project discussion form remains a prototype interaction and does not send or save data.

From the repository root, `make full-up` builds the production frontend image and serves it through Nginx at `http://localhost:5173`. Nginx provides SPA route fallback and proxies `/backend/*` to the FastAPI container.
