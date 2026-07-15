# Battlespace display metrics

Reference for header stat cards, F2T2EA phase counts, and the attention rail. Screenshots live under `docs/images/presentation/metrics/`.

## Header stat cards (`App.svelte`)

| Label | Field | Source | Meaning |
|-------|-------|--------|---------|
| **Entities** | `threat_picture.entity_count` | `GulfWarEngine._threat_counts()` → `len(_entities)` | Correlated tracks on the battlespace picture (OPFOR + coalition + neutral). |
| **Air** | `threat_picture.air_threats` | OPFOR entities with `domain == "AIR"` | Hostile air tracks currently held in the picture. |
| **Surface** | `threat_picture.surface_threats` | OPFOR entities with `domain == "SURFACE"` | Hostile naval/surface tracks. |
| **Tasks** | `threat_picture.active_tasks` | Tasks in lifecycle `NEW` … `ACCEPTED` (excludes `EXECUTED` and `ABORTED`) | Open CAOC task assignments still in progress. |
| **Sim** | `picture.sim_minutes` | Engine clock | Scenario time `T+MM:SS` (floor minutes, rounded seconds). |
| **Update** | (client) | SSE `/api/stream` | Seconds since last picture payload (operator freshness cue). |

### Mapping notes

- **Ground OPFOR** (`domain == "GROUND"`) is counted in `threat_picture.ground_threats` but not shown in the header row today.
- **Tasks** previously counted any non-`EXECUTED` task (including `ABORTED`); fixed to match operator expectation of in-flight work only.

## F2T2EA phase rail (`MissionThreadBar.svelte`)

| Display | Field | Source |
|---------|-------|--------|
| Phase name | `mission_thread.f2t2ea_phases` | Static F2T2EA list |
| Count under phase | `mission_thread.phase_counts[phase]` | Kill-chain rows grouped by current phase |
| Highlighted phase | `mission_thread.dominant_phase` | Phase with highest target count |
| Timeline chips | `mission_thread.timeline_events` | Scenario timeline with `past` / `imminent` / `future` |

## Attention rail (`AttentionRail.svelte`)

Built by `build_attention_queue()` in `mission_ui.py`, merged with advisor suggestions in the API.

| Kind | When it appears | Key fields |
|------|-----------------|------------|
| **TST** | Entity or task promoted time-sensitive (e.g. SCUD launch) | `minutes_remaining`, `target_type`, `detail` |
| **POPUP** | `entity_meta[eid].popup` without active TST **or** `uci.threat.notification` / `uci.route.threat` (bus mode) | Pop-up / route threat — Attention Rail kind for route exposure |
| **TARGET** | HVT with `awaiting_tasking` or `bda_miss` flags | Kill-chain phase + flags |
| **TASK** | Lifecycle `NEW` … `ASSIGNMENT` | Role, blocking reasons, F2T2EA phase |
| **CUSTODY** | Kill-chain in Find/Fix without stale track | Establish custody prompt |
| **AGENT** | Mission advisor suggestion (API merge) | Routed to Decisions tab |

Summary line at top of rail is derived from live queue counts (e.g. `1 time-sensitive · 2 task`).

## Impacted routes (`RouteThreatPanel.svelte`)

Bus / harness picture field `route_threats` (from `uci.route.threat`). Sorted closest-first; distance bands mirror popup-tasker (Strike ≤50 / EJ ≤100 / Jam ≤160 nm). Screenshots: `docs/images/presentation/metrics/metric-route-threats.png`, `docs/images/walkthrough/08-routes-impacted.png`.

| Column | Field |
|--------|-------|
| Route | `route_name` |
| Platforms | `platform_ids` |
| Closest | `closest_approach_nm` |
| Band | derived from closest nm |
| Segs | `impacted_segment_count` / waypoint count |
| Severity | `severity` |
| Threat | `threat_entity_id` |
| Status | `task_ids` present → tasked |

## Route map + segment timeline (`RouteSegmentTimeline.svelte`)

Selecting a route opens the Battlespace map with color-coded polylines (red/orange/purple by band) and a horizontal timeline below the map (onboard + nearby tasks). Support buttons POST `/api/route-threat/support` (harness stub / bus `TASK_REQUEST`). Screenshot: `docs/images/walkthrough/08-route-map-timeline.png`.

## Capturing screenshots

With API on `:8004` and Vite UI on `:5173`:

```bash
python3 scripts/run-gulfwar-local.py   # terminal 1
cd services/battlespace-display/web && npm run dev   # terminal 2
python3 scripts/capture-gulfwar-playwright.py http://127.0.0.1:5173
```

Metric-specific frames are written to `docs/images/presentation/metrics/`.

## Tests

- `tests/test_attention_queue_display.py` — queue kinds, sort order, snapshot contract, header mapping
- `tests/test_tst_task_allocation.py` — TST promotion and attention inclusion
- `tests/test_mission_ui.py` — mission thread and basic queue
