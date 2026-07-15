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

### 2. GitHub access for private deps

Create a fine-grained PAT (or classic with `repo`) that can **read** `mowgli42/o-my` and `mowgli42/o-my-sim`.

In Vercel → Project → Settings → Environment Variables, add for **Production** and **Preview**:

| Name | Value |
|------|--------|
| `GITHUB_TOKEN` | PAT with Contents:Read on both private repos |

Optional alias: `PRIVATE_REPO_TOKEN` (install script accepts either).

Do **not** commit the token. Rotate if it ever leaks in build logs.

If you prefer the Vercel GitHub App instead of HTTPS clone: grant the App access to the private repos in GitHub → Settings → Applications → Vercel, and still set `GITHUB_TOKEN` for the sparse clone in `scripts/vercel-vendor-private.sh`.

### 3. Runtime env (defaults are fine)

`api/index.py` already sets:

- `BATTLESPACE_HARNESS=1`
- `BUS_PICTURE_MODE=0`
- `ADVISOR_EMBEDDED=0`

Override in Vercel only if you intentionally change preview behavior.

### 4. Trigger a deploy

Push to `main` or open a PR. In the build log, confirm:

- `Vendoring o-my` / `Cloning mowgli42/o-my`
- `Vercel vendor ready at .vercel-vendor/`
- `Static assets ready at public/`

Then open the preview URL on desktop or phone — map, Routes tab, attention rail should load from harness fixtures.

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
