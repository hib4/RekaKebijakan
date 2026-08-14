# RekaKebijakan Frontend

The RekaKebijakan frontend is a React, TypeScript, and Vite app for running policy simulations, viewing reports, and interacting with evidence-based results.

## Run Locally

```sh
bun install
bun run dev
```

Open `http://localhost:5173`.

Production build:

```sh
bun run build
bun run preview
```

From the repository root, run the local production full stack with:

```sh
make full-up
```

Nginx serves the frontend at `http://localhost:5173` and proxies API requests to the backend.

## API Configuration

The frontend uses `VITE_API_URL=/backend` by default.

- During development, Vite proxies `/backend` to FastAPI at `http://localhost:5001`.
- In production Docker, Nginx keeps the `/backend` path and proxies it to the backend container.
- This same-origin path is required so the browser sends the authentication cookie.

Copy `.env.example` to `.env` only when you need to change the API path.

## Authentication and Routes

Auth endpoints used by the frontend:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

Public routes:

- `/`
- `/login`
- `/register`

Dashboard, project, simulation, and report routes require a signed-in session. IDs that start with `demo-` continue to use local demo data.

## Verification

```sh
bun run lint
bun run build
bun run test
```
