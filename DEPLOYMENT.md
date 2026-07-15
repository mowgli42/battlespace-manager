# Vercel deployment (battlespace-display)

Public repo [`battlespace-manager`](https://github.com/mowgli42/battlespace-manager) deploys the **battlespace-display** SPA + FastAPI harness API to Vercel. Private [`o-my`](https://github.com/mowgli42/o-my) / [`o-my-sim`](https://github.com/mowgli42/o-my-sim) `uci_common` packages are **vendored at build time** (same dual-path approach as Docker) — they cannot both be `pip install`ed because they share the distribution name `uci-common`.

## What you get

| Surface | Behavior on Vercel |
|---------|-------------------|
| Static UI | Vite build → `public/` (CDN) |
| `/api/*` | FastAPI via `api/index.py` |
| Data | `BATTLESPACE_HARNESS=1` fixtures (no Redis) |
| SSE `/api/stream` | May hit function `maxDuration`; UI also polls `/api/picture` |

Preview URL on every PR once the project is linked; production from `main`.

## One-time setup

### 1. Create / link the Vercel project

1. Import `mowgli42/battlespace-manager` in the [Vercel dashboard](https://vercel.com/new).
2. Framework preset: **Other** (config is in `vercel.json`).
3. Root directory: repository root (leave blank).
4. Confirm Install / Build / Output match `vercel.json` (`scripts/vercel-install.sh`, `scripts/vercel-build.sh`, `public`).

### 2. GitHub access for private deps (optional for harness)

Harness previews work **without** private packages (fixture-only). Vendoring still runs best-effort on Vercel and soft-fails if clone is denied.

To actually vendor `uci_common`, create a fine-grained PAT (or classic with `repo`) that can **read** `mowgli42/o-my` and `mowgli42/o-my-sim`.

In Vercel → Project → Settings → Environment Variables, add for **Production** and **Preview**:

| Name | Value |
|------|--------|
| `PRIVATE_REPO_TOKEN` | PAT with Contents:Read on both private repos |

**Do not use Vercel’s auto `GITHUB_TOKEN` for this** — it only covers the public `battlespace-manager` repo and cannot clone private siblings (that is what made `vercel-install.sh` exit 1).

Aliases: `OMY_READ_TOKEN`, or `GITHUB_TOKEN` if you override it with your PAT (not recommended on Vercel).

Do **not** commit the token. Rotate if it ever leaks in build logs.

### 3. Runtime env (defaults are fine)

`api/index.py` already sets:

- `BATTLESPACE_HARNESS=1`
- `BUS_PICTURE_MODE=0`
- `ADVISOR_EMBEDDED=0`

Override in Vercel only if you intentionally change preview behavior.

### 4. Trigger a deploy

Push to `main` or open a PR. In the build log, confirm:

- `== vercel-install: done ==` (vendor may WARN and continue without private deps)
- `Static assets ready at public/`

Then open the production/preview URL — map, Routes tab, attention rail should load from harness fixtures.

If install still fails, check the log for `npm ci` errors (not vendor). Redeploy after this soft-fail fix lands.

## Local smoke test (no Vercel login)

With sibling `../o-my` and `../o-my-sim` checked out:

```bash
bash scripts/vercel-install.sh
bash scripts/vercel-build.sh
python3 -c "from api.index import app; print(app.title)"
# optional: uvicorn api.index:app --host 127.0.0.1 --port 8004
```

## CLI deploy (optional)

Requires `VERCEL_TOKEN`, and usually `VERCEL_ORG_ID` / `VERCEL_PROJECT_ID`:

```bash
npx vercel link   # once
npx vercel pull --yes --environment=preview
GITHUB_TOKEN=… npx vercel build
npx vercel deploy --prebuilt
```

GitHub Actions workflow `.github/workflows/vercel-deploy.yml` deploys when those secrets are configured; otherwise it no-ops.

## Security notes

- Repo stays public: never put PATs in `vercel.json`, source, or docs examples with real values.
- Vendored trees are build artifacts (`.vercel-vendor/`, `public/`) and are gitignored.
- Harness fixtures are demo data only — not a live COP.

## Scope (this slice)

- **In:** battlespace-display harness preview for mobile / PR review.
- **Out:** entity-display, rf-display, live Redis bus picture (needs a long-lived worker, not serverless).
