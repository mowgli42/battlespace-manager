# RF Display — operator walkthrough

Step-by-step EMSO deconfliction workflow using **rf-display** (`:8082`) with optional cross-link from **battlespace-display** (`:8081`).

Screenshots: [`docs/images/rf-walkthrough/`](images/rf-walkthrough/)

## Prerequisites

```bash
# Sibling repos
repo/o-my/
repo/o-my-sim/
repo/battlespace-manager/

# Capture walkthrough (starts API + UI, advances sim, screenshots)
./scripts/capture-rf-walkthrough.sh
```

Manual run:

```bash
RF_FORCE_MEMORY_BUS=1 python3 scripts/run-rf-display-local.py   # :8005 — live Gulf War engine
./scripts/run-rf-display-ui.sh                                # :8082
```

Harness mode (deterministic sample data, no engine):

```bash
python3 scripts/run-rf-display-harness.py                     # :8005 sample scenario
./scripts/run-rf-display-ui.sh
python3 scripts/verify-rf-display-features.py                 # assert all UI features
python3 scripts/verify-rf-display-features.py --api http://127.0.0.1:8005
```

## Geographic area filter

Open **Geo map** in the header, then draw:

| Tool | How |
|------|-----|
| **Circle** | Click center, then click edge for radius |
| **Zone** | Click polygon vertices · **Close zone** |
| **Route** | Click waypoints · set buffer nm · **Finish route** |

The spectrum columns filter to RF assets inside the area. API: `POST /api/geo-filter`, `DELETE /api/geo-filter`.

## Workflow

### 1. Four-column spectrum overview

Open http://localhost:8082

The main workspace is a **four-column spectrum grid** on a shared frequency axis:

| Column | Contents |
|--------|----------|
| **Radar Threats** | Hostile radars (SA-6 fire control after T+12 SIGINT cue) |
| **Jammers** | Coalition EW platforms; amber **TX** when jamming |
| **Comm** | Commlink network links with directory frequencies |
| **Support** | GPS L1/L2, friendly radars (E-3 AWACS), platform datalinks/SATCOM |

Header stats include threat emitters, active jammers, support asset count, spectrum overlaps, and jam overlaps.

![RF overview](images/rf-walkthrough/01-rf-overview.png)

**Frequency scale:** toggle **Linear**, **Log**, or **Symlog** (default). Symlog handles sub-MHz HF guard nets and GPS L-band on the same axis without compressing HF into a sliver.

**Frequency brush:** drag on the left frequency axis to zoom into a band; **Reset zoom** restores full span.

**JRFL corridors:** violet shaded bands span all four columns at JRFL-protected frequencies (NO_EA darker than EA_REQUIRES_EACA).

**SVG connectors:** red/amber bezier paths link jammed pairs across columns (jammer → comm/support). Enable **All overlaps** to show non-jam band collisions.

![Spectrum connectors](images/rf-walkthrough/05-spectrum-connectors.png)

![Linear scale](images/rf-walkthrough/06-spectrum-linear-scale.png)

Click any asset bar for overlap/jam detail in the footer. **JAMMED** flags appear on comm/support when a friendly jammer overlaps.

### 2. Deconfliction conflict strip

When conflicts exist, a horizontal **conflict strip** below the header lists issues sorted by severity:

| Type | When |
|------|------|
| `jam_comm` | Friendly jam band overlaps active commlink |
| `jam_support` | Jam threatens GPS, friendly radar, or platform RF |
| `jam_radar` | Jam engages hostile radar — verify EACA / JRFL |
| `jrfl_violation` | Jam threatens JRFL-protected frequency |
| `emcon_violation` | Emitter active inside restricted EMCON polygon |
| `reservation_conflict` | Overlapping commlink reservations (o-my EMSO bus) |

Hover connector paths to highlight a single jam relationship; selecting an asset dims unrelated paths.

### 3. JRFL overlay

JRFL chips appear in the bottom strip:

- Protected frequencies (SATCOM L/Ka, Link-16, HF command)
- Restriction class: `NO_EA` or `EA_REQUIRES_EACA`
- EA authority holder from fixture (`EACA_DELEGATED` → RAVEN01 package commander)

### 4. FSPL jam envelopes

EF-111 (`RAVEN01`) jam coverage uses **free-space path loss** with terrain mask. Toggle **Show map** for a compact tactical view of threat radars and jammer positions.

### 5. Battlespace cross-link

From battlespace-display tasking, SEAD rows link to `http://localhost:8082?highlight={entity_id}` — the matching threat radar bar highlights in the **Radar Threats** column.

![SA-6 highlight](images/rf-walkthrough/03-rf-sa6-highlight.png)

## API contract

`GET /api/picture` and SSE `/api/stream` include:

- `spectrum_columns` — four columns with `overlaps_with`, `jammed_by`, `jamming_targets`, `endpoints`
- `support_assets` — GPS, friendly radars, platform RF
- `conflicts` — deconfliction queue

## Related docs

- [RF-DISPLAY-DESIGN.md](RF-DISPLAY-DESIGN.md) — EMSO research synthesis
- [RF-DISPLAY-SPECTRUM-VIZ.md](RF-DISPLAY-SPECTRUM-VIZ.md) — D3 visualization patterns (phase 3)
