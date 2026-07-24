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

The project wizard and non-demo simulation IDs use the Flask API at `http://localhost:5001` by default. Copy `.env.example` to `.env` only when you need to override the API URL or force local demo behavior.

IDs beginning with `demo-` always use local demonstration data and timers. Setting `VITE_DEMO_MODE=true` forces the same local workflow mode for all IDs. The pilot project discussion form remains a prototype interaction and does not send or save data.
