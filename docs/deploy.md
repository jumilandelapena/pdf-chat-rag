# Deploying pdf-chat-rag

The backend is a single Docker image (FastAPI + the embedding model baked in); the frontend is a static Vite build. The recommended free setup is Render for the API and Vercel for the UI, talking to each other cross-origin. Nothing in this repository deploys automatically; the files below are templates.

## Render (backend)

`render.yaml` at the repository root is a Render Blueprint for the API only:

```yaml
services:
  - type: web
    name: pdf-chat-rag-api
    runtime: docker
    plan: free
    region: oregon
    rootDir: backend
    healthCheckPath: /health
```

Steps: Render dashboard > New > Blueprint > pick the repository. Render builds `backend/Dockerfile` (6 to 8 minutes: torch and the model are downloaded at build time), prompts for `ANTHROPIC_API_KEY` (declared with `sync: false`), and starts the service on the `PORT` env var (8000). Set `CORS_ORIGINS` to your Vercel origin, exactly, without a trailing slash.

Be honest with yourself about the Free plan:

- 0.1 CPU and 512 MB RAM. torch plus sentence-transformers sit at roughly 350 to 500 MB resident, so the service runs but is close to the limit and may be killed under load. Keep `WEB_CONCURRENCY=1`.
- The disk is ephemeral: uploads, the SQLite database and the Chroma index vanish on every deploy or restart.
- Services spin down after 15 minutes without traffic and take about a minute to wake. The frontend polls `/health` and shows a "Waking up the server" banner until the API answers.
- 750 free instance hours and 500 build minutes per month; the health check must answer within 5 seconds (`/health` does no model work).

The paid path that removes those limits: `plan: starter` or larger (for example `1c-2g`, about $25 per month), plus a persistent disk:

```yaml
    plan: 1c-2g
    disk:
      name: data
      mountPath: /var/data
      sizeGB: 1
    envVars:
      - key: DATA_DIR
        value: /var/data
```

The image runs as uid 10001; if the mounted disk is not writable, set `DATA_DIR` to a sub-directory the service can create, or run a one-off `chown` from the Render shell.

Test the deployed API with a streamed request:

```bash
curl -N -X POST https://<service>.onrender.com/chats/<chat-id>/messages \
  -H "Content-Type: application/json" -d '{"content":"Which error code does a teapot return?"}'
```

## Vercel (frontend)

1. Import the repository, set the Root Directory to `frontend` and keep the Vite framework preset.
2. Add the environment variable `VITE_API_BASE_URL=https://<service>.onrender.com` (no trailing slash) for Production and Preview. It is baked in at build time, so redeploy after changing it.
3. `frontend/vercel.json` rewrites every path to `index.html` for the single-page app.

The browser then calls Render directly. A Vercel rewrite proxy is deliberately not used: Vercel caps proxied requests at 120 seconds and may cache upstream responses, both of which break Server-Sent Events.

## CORS

The backend allows exactly the origins listed in `CORS_ORIGINS` (comma-separated), with no credentials. Add the production origin and, if you use Vercel preview deployments, each preview origin you need (or extend `CORSMiddleware` with `allow_origin_regex` for `https://.*\.vercel\.app`).

## Alternatives

- Docker Compose on any VM: `docker compose up --build` with a `.env` next to it (see the README). This is the only setup that keeps data between restarts for free.
- Hugging Face Spaces (Docker) now requires a PRO account for custom images; Fly.io and Railway have no usable free tier for a 2 GB image.

## Checklist

- [ ] `ANTHROPIC_API_KEY` set on Render, never committed.
- [ ] `CORS_ORIGINS` matches the Vercel origin exactly.
- [ ] `VITE_API_BASE_URL` set on Vercel and the frontend redeployed.
- [ ] `/health` returns `{"status":"ok", ...}` and `/docs` loads on the Render URL.
- [ ] A streamed chat works from the Vercel URL (watch the Network tab for `text/event-stream`).
