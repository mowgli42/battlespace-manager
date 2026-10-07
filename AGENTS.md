# battlespace-manager

Operator web displays for the Open Arsenal / OMS / UCI stack (entity map, Gulf War F2T2EA COP, RF/EMSO). Engines and publishers stay in sibling repos.
Stack: Svelte 5 + Vite, FastAPI, Redis bus, Leaflet (MapLibre is a later spike — ADR 001).
Posture: ponytail (repo created 2026-06-28, older than 30 days).
Shared health pack: `.cursor/skills/` and `.cursor/rules/`. Do not duplicate it here.
Live harness: https://battlespace-manager.vercel.app

## Commands

- Entity demo: `./scripts/run-entity-display-local.sh` → http://127.0.0.1:8930
- Battlespace harness: `python3 scripts/run-battlespace-local.py` then `./scripts/run-battlespace-ui.sh` → :8031 / :8931
- Bus picture (no embedded engine): `REDIS_URL=redis://127.0.0.1:6379/0 BUS_PICTURE_MODE=1 ./scripts/run-battlespace-bus.sh`
- RF harness: `python3 scripts/run-rf-display-harness.py` then `./scripts/run-rf-display-ui.sh` → :8032 / :8932
- Portal: `python3 scripts/run-display-portal.py` → http://127.0.0.1:8939
- All display tests: `./scripts/run-all-tests.sh`
- Gherkin alignment: `python3 scripts/check-gherkin-alignment.py`
- Secrets: `bash scripts/scan-secrets.sh .`
- Remaining work: `bd ready` (Beads). Do not invent a second tracker.

Sibling `uci_common` via `scripts/env.sh` (`OMY_ROOT` / `OMYSIM_ROOT`). Ports match o-my `docs/PORTS.md`: entity 8030/8930, battlespace 8031/8931, rf 8032/8932, portal 8939.

## Hard prohibitions

- Do not commit private keys, `*-key.pem`, `*.key`, `.env` secrets, or `BEGIN … PRIVATE KEY`. Generate locally; gitignore keys. Public certs may stay.
- Do not add simulation engines, sensor sims, or scenario-director here. Those stay in o-my-sim. This repo subscribes and displays.
- Do not treat embedded `GulfWarEngine` as cross-stack truth. Use `BUS_PICTURE_MODE=1` when o-my processors are up.
- Do not invent ports, UCI topics, or scripts that are not in this tree or `docs/OPENSPEC.md`.
- Do not rewrite OpenSpec / `features/` / Beads to match a hoped-for phase. Update them only when the code already changed.

## Verify by change type

| Change | Check |
| --- | --- |
| UI (`services/*/web`) | matching display script above; vitest in that web package |
| API (`services/*/api`) | `./scripts/run-all-tests.sh` or the display unittest path it calls |
| Spec | `python3 scripts/check-gherkin-alignment.py`; `docs/OPENSPEC.md` still true |
| Deploy | https://battlespace-manager.vercel.app returns 200 |
| Secrets | `bash scripts/scan-secrets.sh .` |

## Source of truth

- Behavior: `docs/OPENSPEC.md` and `features/`
- Boundaries: `docs/adr/002-repo-boundaries.md` and `docs/adr/001-tactical-cop-stack.md`
- Remaining work: Beads (`bd`) and GitHub issues
- Demo evidence: `docs/images/displays/` and `docs/COP-OPERATOR-WORKFLOW.md`

## House vocabulary

- Harness — embedded/sample picture (`*_HARNESS=1` or `run-*-local`). Not the cross-stack bus.
- Bus picture — COP from Redis `uci.*` with `BUS_PICTURE_MODE=1`. Do not call this the engine.
- Attention rail — POPUP / TST cues from `uci.route.threat` and `uci.threat.notification`.
- F2T2EA kanban — Find → Assess columns; assign by dragging to Decisions. Do not restore an All list.
- Display portal — :8939 status for the three UIs. Rows stay offline until those processes are up.

## Good / bad

Bad: embedding GulfWarEngine as the production picture path.
Good: `scripts/run-battlespace-bus.sh` subscribing to `uci.correlated.entity` and `uci.f2t2ea.state`.

## Borrowed patterns

- hard-prohibition — apache/airflow via ossrules.md (engines stay out; keys stay out)
- verification-matrix — apache/airflow via ossrules.md (UI vs API vs spec vs deploy)
- single-source — browser-use/browser-use via ossrules.md (OpenSpec + features, not a copy)
- house-vocabulary — debpalash/VoiceStudio via ossrules.md (harness vs bus picture)
