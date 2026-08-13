# COP UCI contract — planned vs actual, EOB overlay, in-mission C2

**This repo is SUBSCRIBER** for operational data. Never system of record. Hub: [o-my-mission-plan UCI-CONTRACTS.md](https://github.com/mowgli42/o-my-mission-plan/blob/cursor/mission-plan-uci-flow-1dca/docs/UCI-CONTRACTS.md) hop 5. IxDF: o-my-mission-plan `docs/IXDF-FEEDBACK.md`. Extends GitHub **#14** (popup / UCI tasking) — do not replace it.

---

## Ingest (must persist enough to draw)

| Topic | MessageType | Required fields | Draw / UI |
|-------|-------------|-----------------|-----------|
| `uci.route.plan` | `RoutePlan` | PlatformID, RouteName, Waypoint[] name/lat/lon | **Dashed** planned polyline |
| `uci.platform.status` | PlatformStatus | PlatformID, lat/lon, RouteName, MissionPlanID | **Solid** actual breadcrumb |
| `uci.mission.plan.execution` | `MissionPlanExecutionStatus` | PlatformID, State, DeviationSeverity, CrossTrackNm | Break mark at OFF_PLAN/CRITICAL; HUD chip |
| `uci.threat.notification` | program | Kind, Title, Tone, Icon | Attention rail |
| `uci.oob` / pre-briefed `uci.entity` | `OrderOfBattle` / Entity | EntityID, position, category | Static IADS overlay (not a live track) |
| `uci.task.plan` / `uci.task` / `uci.task.status` | Task* | TaskID, Role, TargetEntityID, status | Decisions queue; onboard vs nearby tasks (#14) |
| `uci.dmpi` | `DMPI` | DMPI_ID, TargetEntityID, lat/lon | Aimpoint marker (optional) |
| `uci.prioritization` | `Prioritization` | Item Rank + EntityID | Optional priority column |
| `uci.f2t2ea.state` | program | phase | Kill-chain (existing) |

Ignore OK: planner COA internals, fuel GO/NO-GO proofs, fuzzy `original_row`.

CorrelationID = MissionPlanID. Do not invent tracks or tasks.

---

## Attention kinds (add)

Today: `TST`, `POPUP`, `TARGET`, `TASK`, `CUSTODY`, `AGENT`.

| Kind | Source | Tone + icon + text (never color alone) |
|------|--------|----------------------------------------|
| `PLAN_DEVIATION` | ExecutionStatus WATCH/OFF_PLAN/CRITICAL or notification Kind | watch/break/alert + “Off plan N nm” |
| `RETASK` | TaskCommand in flight until TaskStatus ACK | fork + “Retask accepted/rejected” |

Thresholds (do not fork): WATCH 2 nm, OFF_PLAN 5 nm, CRITICAL 12 nm.

---

## Send: TaskCommand (closes G4)

**Do not** HTTP POST to o-my-sim `:8018` in bus picture mode. Publish:

| Field | Required |
|-------|----------|
| `TaskCommandID` | yes |
| `MissionPlanID` | yes (CorrelationID) |
| `PlatformID` | yes |
| `Role` | yes |
| `TargetEntityID` | yes |
| `Latitude` `Longitude` | yes |
| `Reason` | no |
| `ReplaceTaskID` | no |

Wait for `TaskStatus`. Optimistic UI: “Sending…”. Rejected → show reason. Kinematic change is `RouteModificationRequest` → new RoutePlan version, not a silent overwrite.

`TaskCancelCommand` requires `TaskCancelCommandStatus`.

Popup-impacted routes (#14) SHALL use `uci.route.plan` / `uci.platform.route` + `uci.route.threat` + `uci.task*` — same bus, no hard-coded geometry.

---

## Picture contract additions (planned)

`picture_contract.py` SHOULD grow optional keys (backward compatible):

- `planned_routes[]` — from RoutePlan
- `attention_queue[].kind` includes `PLAN_DEVIATION`, `RETASK`
- `eob_sites[]` — pre-briefed OOB (distinct from `entities[]` live tracks)

Harness fixtures MAY stub these; bus picture mode MUST populate from topics above.
