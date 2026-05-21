# TradingAgents Web UI

This branch adds a sidecar web workspace instead of editing the upstream engine:

- `tradingagents_web/`: FastAPI API, run store, and subprocess runner.
- `frontend/`: Vue 3, TypeScript, Vite, and Element Plus interface.
- Runtime data lives under `~/.tradingagents/web` by default.

Run locally:

```bash
uv sync
npm install --prefix frontend
npm run build --prefix frontend
uv run tradingagents-web
```

Then open `http://127.0.0.1:8000`.

LAN access:

```bash
uv run tradingagents-web --host 0.0.0.0 --port 8000
```

Then open `http://<your-mac-lan-ip>:8000` from another device on the same network.
Keep the default `127.0.0.1` binding when you do not need LAN access.

For frontend development:

```bash
uv run tradingagents-web
npm run dev --prefix frontend
```

Then open `http://127.0.0.1:5173`.

For LAN frontend development:

```bash
uv run tradingagents-web --host 0.0.0.0 --port 8000
npm run dev:lan --prefix frontend
```
