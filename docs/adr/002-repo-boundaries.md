# ADR 002: Repository boundaries (o-my / o-my-sim / battlespace-manager)

**Status:** Accepted  
**Date:** 2026-06-30  
**Supersedes:** informal split only (no prior ADR on ownership)

## Context

The tactical COP stack spans three repos. Contract tiers are documented in `o-my/docs/INTERFACE.md`, but runtime coupling still relies on sibling-directory layout, merged `PYTHONPATH`, subprocess delegation, and duplicated `uci_common` modules. That made merges painful (e.g. sim-control and kill-chain PRs conflicting with battlespace-display extraction).

## Decision — one concern per repo

| Repo | Owns | Must not own |
|------|------|--------------|
| **o-my** | C2 core: Redis bus, `uci.entity.*`, commlink directory/status, ADS-B pipeline, service control plane, `omy-c2-core-1` contract | Gulf War scenario engine, operator Svelte displays, sim sensors |
| **o-my-sim** | Simulation: `GulfWarEngine`, scenario fixtures, sensor/correlator/tasking/kill-chain microservices, sim-control panel (`:8090`), `omy-gulfwar-1` extension topics | FastAPI picture APIs, battlespace/entity display UIs |
| **battlespace-manager** | Operator displays: `entity-display`, `battlespace-display`, picture/SSE HTTP contracts, display-only logic (`display_logic.py`, symbology) | Engine tick loop, feed simulators, scenario timeline authoring |

### Integration surfaces (allowed coupling)

1. **Redis UCI topics** — displays subscribe; sim publishes (`uci.scenario.*`, threat picture, tasks).
2. **Pinned compat manifests** — `compat/tested-against.json` in each repo; `scripts/check-omy-compat.py` must **fail** CI when versions drift.
3. **HTTP picture contract** — `GET /api/picture`, `GET /api/stream`; validated by `picture_contract.py` + unit tests.
4. **Embedded dev mode** — battlespace-manager may import `GulfWarEngine` for local demo only; production path is Redis + o-my-sim services.

### Forbidden patterns (remove over time)

- Duplicate `uci_common` modules in o-my-sim that already exist in o-my (`bus.py`, `topics.py`, commlink XML).
- `entity-display` in o-my `docker-compose.yml` (canonical UI is battlespace-manager).
- o-my-sim tests importing `battlespace-display/api/app/main.py` (move to battlespace-manager or a shared contract fixture).
- Subprocess delegation wrappers (`run-gulfwar-local.py` → battlespace-manager) as the long-term API; replace with documented stack compose or pinned pip deps.
- Cross-repo screenshot scripts duplicated in o-my-sim after extraction.

## Target packaging (Phase 1 — next)

```
pip install omy-uci-core==0.2.0      # from o-my packages/uci_common
pip install omy-uci-gulfwar==0.1.0   # from o-my-sim, depends on core
```

battlespace-manager `requirements.txt` / Docker images install both wheels instead of `PYTHONPATH` sibling hacks.

## Testing workflow (enforced now)

| Step | Command | When |
|------|---------|------|
| Display unit + contract tests | `./scripts/run-all-tests.sh` | Every battlespace-manager change |
| Stack compat gate | `./scripts/check-omy-compat.py` | CI + before release |
| Visual regression (tasking T+0) | `./scripts/capture-tasking-t0.sh` | After tasking/picture changes |
| Full operator deck | `./scripts/demo-presentation.sh` | Release / doc refresh |

CI (`.github/workflows/ci.yml`) checks out pinned sibling repos and runs `run-all-tests.sh`.

## Port allocation

| Port | Service | Repo |
|------|---------|------|
| 6379 | Redis | shared |
| 8003 | entity-display API | battlespace-manager |
| 8004 | battlespace-display API / embedded engine | battlespace-manager (+ o-my-sim engine lib) |
| 8005 | service-control-plane | o-my |
| 8080 | entity-display UI | battlespace-manager |
| 8081 | battlespace-display UI | battlespace-manager |
| 8090 | sim-control UI | o-my-sim |

o-my `commlink-status` should move off `:8004` when both stacks run together (documented conflict).

## Consequences

- **Positive:** Clear ownership; display fixes stay in battlespace-manager; sim fixes stay in o-my-sim; merges do not re-delete moved trees.
- **Negative:** Short-term still requires sibling clones for embedded dev until pip packages land.
- **Action:** Track dedup of `uci_common` and removal of o-my `entity-display` compose profile in beads.
