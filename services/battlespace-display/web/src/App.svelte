<script>
  import { onMount, onDestroy } from "svelte";
  import L from "leaflet";
  import KillChainPanel from "./KillChainPanel.svelte";
  import TaskingPanel from "./TaskingPanel.svelte";
  import TracksPanel from "./TracksPanel.svelte";
  import SourcesPanel from "./SourcesPanel.svelte";
  import AssessPanel from "./AssessPanel.svelte";
  import MissionThreadBar from "./MissionThreadBar.svelte";
  import AttentionRail from "./AttentionRail.svelte";
  import TimelinePanel from "./TimelinePanel.svelte";
  import RouteThreatPanel from "./RouteThreatPanel.svelte";
  import RouteSegmentTimeline from "./RouteSegmentTimeline.svelte";
  import { entityPopupHtml, getOrCreateMilIcon } from "./lib/milSymbol.js";
  import { buildImpactSegments } from "./lib/routeImpact.js";

  const MAP_ENTITY_CAP = 350;
  const TABS = [
    { id: "map", label: "Battlespace", key: "1" },
    { id: "routes", label: "Routes", key: "8" },
    { id: "timeline", label: "Timeline", key: "7" },
    { id: "tracks", label: "Tracks", key: "2" },
    { id: "sources", label: "Sources", key: "3" },
    { id: "decisions", label: "Decisions", key: "4" },
    { id: "assess", label: "Assess", key: "5" },
    { id: "killchain", label: "Kill chain", key: "6" },
  ];

  let tab = $state("map");
  let selectedEntityId = $state(null);
  let killChainPhaseFilter = $state(null);
  let picture = $state({
    sim_minutes: 0,
    narrative: "",
    entities: [],
    cues: [],
    coalition_platforms: [],
    fkcm_targets: [],
    track_history: {},
    threat_picture: {},
    fusion_rows: [],
    caoc_tasks: [],
    mission_thread: {},
    entity_registry: [],
    feed_status: [],
    attention_queue: [],
    route_threats: [],
    bda_items: [],
    advisor_suggestions: [],
    advisor_isr_assignments: [],
    oms_ai_services: [],
    oms_ai_summary: {},
    timeline_view: {},
  });
  /** Top-level $state arrays — nested picture.platforms/task_rows do not trigger Svelte 5 template updates. */
  let omsPlatforms = $state([]);
  let caocTaskRows = $state([]);
  let routeThreatRows = $state([]);
  let routeGeometries = $state({});
  let selectedRouteName = $state(null);
  let selectedSegmentIndex = $state(null);
  let timelineAxis = $state("distance");
  let routeLayers = [];
  let supportFlash = $state("");
  let markers = new Map();
  let cueLayers = [];
  let source = null;
  let pictureRetryTimer = null;
  let map;
  let apiConnected = $state(false);
  let harnessMode = $state(false);
  let lastPictureMs = $state(null);

  function narrativeStatus() {
    if (!apiConnected) {
      return "No API connection — start python3 scripts/run-gulfwar-local.py (port 8004), then refresh. UI must be on http://localhost:5173";
    }
    if (picture.narrative) return picture.narrative;
    if (picture.mission_thread?.narrative) return picture.mission_thread.narrative;
    return "Scenario loaded — sim advancing…";
  }

  function selectEntity(id) {
    selectedEntityId = id;
    const ent = picture.entities?.find((e) => e.entity_id === id);
    if (ent && map) {
      map.panTo([ent.latitude, ent.longitude], { animate: true });
      tab = "map";
      setTimeout(updateMap, 50);
    }
  }

  function onAttention(item) {
    if (item.kind === "AGENT") {
      tab = "decisions";
      if (item.entity_id) selectEntity(item.entity_id);
      return;
    }
    if (item.entity_id) selectEntity(item.entity_id);
    if (item.kind === "TASK" || item.kind === "TST") tab = "decisions";
    else if (item.kind === "POPUP") {
      tab = "routes";
      if (item.route_name) selectedRouteName = item.route_name;
      if (item.entity_id) selectedEntityId = item.entity_id;
    } else if (item.kind === "TARGET") {
      tab = "killchain";
      if (item.entity_id) selectedEntityId = item.entity_id;
    }
  }

  function onRouteThreatSelect(row) {
    selectedRouteName = row.route_name || null;
    selectedSegmentIndex = null;
    if (row.threat_entity_id) selectEntity(row.threat_entity_id);
    tab = "map";
    setTimeout(() => {
      updateMap();
      fitSelectedRoute();
    }, 80);
  }

  function selectedRouteThreat() {
    return (
      routeThreatRows.find((r) => r.route_name === selectedRouteName) ||
      routeThreatRows[0] ||
      null
    );
  }

  function waypointsForRoute(routeName) {
    const threat = routeThreatRows.find((r) => r.route_name === routeName);
    if (threat?.waypoints?.length) return threat.waypoints;
    const geom = routeGeometries[routeName];
    return geom?.waypoints || [];
  }

  let impactModel = $derived.by(() => {
    const row = selectedRouteThreat();
    if (!row) return null;
    const wps = waypointsForRoute(row.route_name);
    if (!wps.length) return null;
    return {
      row,
      ...buildImpactSegments(wps, row.latitude, row.longitude),
    };
  });

  function clearRouteLayers() {
    if (!map) return;
    for (const layer of routeLayers) {
      try {
        map.removeLayer(layer);
      } catch (_) {}
    }
    routeLayers = [];
  }

  function fitSelectedRoute() {
    if (!map || !impactModel?.waypoints?.length) return;
    try {
      const bounds = L.latLngBounds(impactModel.waypoints);
      if (impactModel.row?.latitude != null) {
        bounds.extend([impactModel.row.latitude, impactModel.row.longitude]);
      }
      map.fitBounds(bounds.pad(0.2), { animate: true, maxZoom: 9 });
    } catch (_) {}
  }

  async function onRequestSupport(kind) {
    const row = selectedRouteThreat();
    if (!row) return;
    const role = { STRIKE: "STRIKE", EJ: "SEAD", JAM: "CAP" }[kind] || kind;
    try {
      const r = await fetch("/api/route-threat/support", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          threat_entity_id: row.threat_entity_id,
          route_name: row.route_name,
          role,
          band: kind,
          closest_approach_nm: row.closest_approach_nm,
        }),
      });
      const data = await r.json().catch(() => ({}));
      supportFlash = r.ok
        ? `Queued ${kind} support for ${row.threat_entity_id} (${data.task_id || "ok"})`
        : `Support request failed (${r.status})`;
    } catch (e) {
      supportFlash = `Support request error: ${e}`;
    }
    setTimeout(() => (supportFlash = ""), 5000);
  }

  function onPhaseClick(ph) {
    tab = "killchain";
    killChainPhaseFilter = killChainPhaseFilter === ph ? null : ph;
  }

  function entityLabel(e) {
    return `${e.platform_type || e.entity_id} · ${Math.round((e.confidence || 0) * 100)}%`;
  }

  function upsertEntityMarker(e) {
    const id = e.entity_id;
    const sel = selectedEntityId === id;
    const latlng = [e.latitude, e.longitude];
    const icon = getOrCreateMilIcon(e, sel);
    const label = entityLabel(e);

    if (markers.has(id)) {
      const m = markers.get(id);
      m.setLatLng(latlng);
      const prevUrl = m.options?.icon?.options?.iconUrl;
      if (prevUrl !== icon.options.iconUrl) {
        m.setIcon(icon);
      }
      m.setPopupContent(entityPopupHtml(e));
    } else {
      const m = L.marker(latlng, { icon })
        .bindTooltip(label, { direction: "top", opacity: 0.9 })
        .bindPopup(entityPopupHtml(e));
      m.on("click", () => selectEntity(id));
      m.addTo(map);
      markers.set(id, m);
    }
  }

  function updateMap() {
    if (!map) return;
    const entities = (picture.entities || []).slice(0, MAP_ENTITY_CAP);
    const seen = new Set();
    for (const e of entities) {
      seen.add(e.entity_id);
      upsertEntityMarker(e);
    }
    for (const [id, m] of markers) {
      if (id.startsWith("plt-")) continue;
      if (!seen.has(id)) {
        map.removeLayer(m);
        markers.delete(id);
      }
    }
    for (const layer of cueLayers) map.removeLayer(layer);
    cueLayers = [];
    for (const c of picture.cues || []) {
      const center = [c.latitude, c.longitude];
      try {
        const circ = L.circle(center, { radius: 8000, color: "#a78bfa", weight: 1, fillOpacity: 0.08 });
        circ.addTo(map);
        cueLayers.push(circ);
      } catch (_) {}
    }
    for (const p of omsPlatforms) {
      const id = `plt-${p.platform_id}`;
      if (markers.has(id)) markers.get(id).setLatLng([p.latitude, p.longitude]);
      else {
        const m = L.circleMarker([p.latitude, p.longitude], {
          radius: 4,
          fillColor: "#00d4ff",
          color: "#00d4ff",
          weight: 1,
          fillOpacity: 0.7,
        }).bindTooltip(
          `${p.callsign} · ${p.platform_type}${p.operational_role ? " · " + p.operational_role : ""}${p.route_name ? " · " + p.route_name : ""}${p.kill_chain_phase ? " · F2T2EA " + p.kill_chain_phase : ""}`
        );
        m.addTo(map);
        markers.set(id, m);
      }
    }

    clearRouteLayers();
    const drawRows = selectedRouteName
      ? routeThreatRows.filter((r) => r.route_name === selectedRouteName)
      : routeThreatRows.slice(0, 3);
    for (const row of drawRows) {
      const wps = waypointsForRoute(row.route_name);
      if (wps.length < 2) continue;
      const impact = buildImpactSegments(wps, row.latitude, row.longitude);
      for (const seg of impact.segments) {
        const weight =
          selectedRouteName === row.route_name
            ? selectedSegmentIndex === seg.index
              ? 7
              : 5
            : 3;
        const line = L.polyline(seg.latlngs, {
          color: seg.color,
          weight,
          opacity: seg.impacted ? 0.95 : 0.45,
        }).bindTooltip(
          `${row.route_name} seg ${seg.index + 1} · ${seg.closest_nm.toFixed(1)} nm · ${seg.band}`,
          { sticky: true }
        );
        line.on("click", () => {
          selectedRouteName = row.route_name;
          selectedSegmentIndex = seg.index;
          if (row.threat_entity_id) selectedEntityId = row.threat_entity_id;
        });
        line.addTo(map);
        routeLayers.push(line);
      }
      if (row.latitude != null && row.longitude != null) {
        const threatMark = L.circleMarker([row.latitude, row.longitude], {
          radius: selectedRouteName === row.route_name ? 8 : 5,
          color: "#ef4444",
          fillColor: "#ef4444",
          fillOpacity: 0.85,
          weight: 2,
        }).bindTooltip(`${row.threat_entity_id} · ${Number(row.closest_approach_nm).toFixed(1)} nm`);
        threatMark.addTo(map);
        routeLayers.push(threatMark);
      }
    }
  }

  function applyPayload(data) {
    picture = {
      sim_minutes: data.sim_minutes ?? 0,
      narrative: data.narrative ?? "",
      entities: data.entities ?? [],
      cues: data.cues ?? [],
      coalition_platforms: data.platforms ?? [],
      platforms: data.platforms ?? [],
      caoc_tasks: data.task_rows ?? [],
      fkcm_targets: data.fkcm_targets ?? [],
      track_history: data.track_history ?? {},
      threat_picture: data.threat_picture ?? {},
      fusion_rows: data.fusion_rows ?? [],
      mission_thread: data.mission_thread ?? {},
      entity_registry: data.entity_registry ?? [],
      feed_status: data.feed_status ?? [],
      attention_queue: data.attention_queue ?? [],
      route_threats: data.route_threats ?? [],
      route_geometries: data.route_geometries ?? {},
      bda_items: data.bda_items ?? [],
      advisor_suggestions: data.advisor_suggestions ?? [],
      advisor_isr_assignments: data.advisor_isr_assignments ?? [],
      oms_ai_services: data.oms_ai_services ?? [],
      oms_ai_summary: data.oms_ai_summary ?? {},
      timeline_view: data.timeline_view ?? {},
    };
    harnessMode = Boolean(data.harness_mode);
    omsPlatforms = picture.coalition_platforms;
    caocTaskRows = picture.caoc_tasks;
    routeThreatRows = picture.route_threats;
    routeGeometries = picture.route_geometries || {};
    lastPictureMs = Date.now();
    if (tab === "map") updateMap();
  }

  function connectStream() {
    source = new EventSource("/api/stream");
    source.onopen = () => {
      apiConnected = true;
    };
    source.onmessage = (ev) => {
      apiConnected = true;
      try {
        applyPayload(JSON.parse(ev.data));
      } catch (e) {
        console.warn(e);
      }
    };
    source.onerror = () => {
      if (!lastPictureMs || Date.now() - lastPictureMs > 8000) {
        apiConnected = false;
      }
      source?.close();
      setTimeout(connectStream, 2000);
    };
  }

  function isTextInputTarget(el) {
    if (!el || !(el instanceof HTMLElement)) return false;
    const tag = el.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
    return el.isContentEditable;
  }

  function onKey(ev) {
    if (isTextInputTarget(ev.target)) return;
    const t = TABS.find((x) => x.key === ev.key);
    if (t) {
      ev.preventDefault();
      tab = t.id;
    }
  }

  async function loadPicture() {
    try {
      const r = await fetch("/api/picture");
      if (!r.ok) throw new Error(String(r.status));
      applyPayload(await r.json());
      apiConnected = true;
      return true;
    } catch {
      apiConnected = false;
      return false;
    }
  }

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tab");
    const valid = TABS.map((x) => x.id);
    if (t && valid.includes(t)) tab = t;
    if (t === "fusion") tab = "sources";
    if (t === "tasking") tab = "decisions";
    const phase = params.get("phase");
    if (phase && tab === "killchain") killChainPhaseFilter = phase;
    window.addEventListener("keydown", onKey);
    map = L.map("map", { zoomControl: true, preferCanvas: true }).setView([29.75, 47.75], 7);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "CARTO · OSM",
      maxZoom: 12,
    }).addTo(map);
    connectStream();
    void loadPicture();
    pictureRetryTimer = setInterval(() => {
      void loadPicture().then((ok) => {
        if (ok && pictureRetryTimer) {
          clearInterval(pictureRetryTimer);
          pictureRetryTimer = null;
        }
      });
    }, 2000);
  });

  onDestroy(() => {
    window.removeEventListener("keydown", onKey);
    if (pictureRetryTimer) clearInterval(pictureRetryTimer);
    source?.close();
    map?.remove();
  });

  $effect(() => {
    selectedEntityId;
    selectedRouteName;
    selectedSegmentIndex;
    if (tab === "map" && map) {
      setTimeout(() => {
        map.invalidateSize();
        updateMap();
      }, 80);
    }
  });

  let tp = $derived(picture.threat_picture || {});
  let mapLabel = $derived(
    (picture.entities?.length || 0) > MAP_ENTITY_CAP
      ? ` (map ${MAP_ENTITY_CAP}/${picture.entities.length})`
      : ""
  );
</script>

<div class="shell">
  <header class="app-header">
    <div class="header-left">
      <span class="live-badge" aria-live="polite">● LIVE</span>
      {#if harnessMode}
        <span class="harness-badge">Harness</span>
      {/if}
      <h1>CAOC · DESERT STORM · F2T2EA MONITOR</h1>
    </div>
    <div class="stat-cards" role="group" aria-label="Mission metrics">
      <div class="stat"><span class="stat-val">{tp.entity_count ?? 0}</span><span class="stat-lbl">Entities</span></div>
      <div class="stat"><span class="stat-val">{tp.air_threats ?? 0}</span><span class="stat-lbl">Air</span></div>
      <div class="stat"><span class="stat-val">{tp.surface_threats ?? 0}</span><span class="stat-lbl">Surface</span></div>
      <div class="stat stat-click" role="button" tabindex="0" onclick={() => (tab = "timeline")} onkeydown={(e) => e.key === "Enter" && (tab = "timeline")} title="Open timeline"><span class="stat-val">{tp.active_tasks ?? 0}</span><span class="stat-lbl">Tasks</span></div>
      <div class="stat"><span class="stat-val zulu">T+{Math.floor(picture.sim_minutes ?? 0)}:{String(Math.round(((picture.sim_minutes ?? 0) % 1) * 60)).padStart(2, "0")}</span><span class="stat-lbl">Sim</span></div>
      {#if lastPictureMs}
        <div class="stat" title="Time since last picture update"><span class="stat-val stat-latency">{Math.max(0, Math.round((Date.now() - lastPictureMs) / 1000))}s</span><span class="stat-lbl">Update</span></div>
      {/if}
    </div>
    <span class="class-banner">UNCLASS // SIMULATION · Keys 1–8 tabs</span>
  </header>

  <MissionThreadBar {picture} onPhaseClick={onPhaseClick} />

  <nav class="tabs" aria-label="Main views">
    {#each TABS as t (t.id)}
      <button type="button" class:active={tab === t.id} onclick={() => (tab = t.id)} title="Shortcut {t.key}">
        <kbd>{t.key}</kbd> {t.label}
      </button>
    {/each}
  </nav>

  <div class="workspace">
    <AttentionRail
      items={picture.attention_queue || []}
      {selectedEntityId}
      onSelect={onAttention}
    />
    <div class="content">
      <div class="panel map-panel" class:active={tab === "map"}>
        <div class="map-stack">
          <div id="map"></div>
          <div class="narrative" class:narrative-warn={!apiConnected} role="status">
            {narrativeStatus()}
            {#if selectedRouteName}
              <span class="route-cue"> · Route {selectedRouteName} · north-up · click segment for timeline</span>
            {/if}
            {#if supportFlash}
              <span class="route-cue support"> · {supportFlash}</span>
            {/if}
          </div>
        </div>
        {#if impactModel}
          <RouteSegmentTimeline
            routeName={impactModel.row.route_name}
            threatEntityId={impactModel.row.threat_entity_id}
            closestNm={impactModel.closestNm ?? impactModel.row.closest_approach_nm}
            severity={impactModel.row.severity}
            segments={impactModel.segments}
            cumulativeNm={impactModel.cumulativeNm}
            waypoints={impactModel.waypoints}
            closestIndex={impactModel.closestIndex}
            selectedSegmentIndex={selectedSegmentIndex}
            onboardTasks={caocTaskRows.filter(
              (t) => t.route_name === impactModel.row.route_name || (impactModel.row.task_ids || []).includes(t.task_id)
            )}
            nearbyTasks={caocTaskRows.filter(
              (t) => t.route_name && t.route_name !== impactModel.row.route_name
            )}
            axisMode={timelineAxis}
            onSelectSegment={(seg) => {
              selectedSegmentIndex = seg.index;
            }}
            onRequestSupport={onRequestSupport}
            onAxisChange={(mode) => (timelineAxis = mode)}
          />
        {/if}
      </div>
      <div class="panel grid-panel" class:active={tab === "routes"}>
        <RouteThreatPanel
          routeThreats={routeThreatRows}
          {selectedRouteName}
          {selectedEntityId}
          onSelect={onRouteThreatSelect}
        />
      </div>
      <div class="panel grid-panel" class:active={tab === "timeline"}>
        <TimelinePanel
          {picture}
          onSelectEntity={selectEntity}
          onOpenDecisions={() => (tab = "decisions")}
        />
      </div>
      <div class="panel grid-panel" class:active={tab === "tracks"}>
        <TracksPanel {picture} bind:selectedEntityId onSelectEntity={selectEntity} />
      </div>
      <div class="panel grid-panel" class:active={tab === "sources"}>
        <SourcesPanel {picture} bind:selectedEntityId onSelectEntity={selectEntity} />
      </div>
      <div class="panel grid-panel" class:active={tab === "decisions"}>
        <TaskingPanel
          platforms={omsPlatforms}
          taskRows={caocTaskRows}
          {harnessMode}
          advisorSuggestions={picture.advisor_suggestions ?? []}
          omsAiServices={picture.oms_ai_services ?? []}
          omsAiSummary={picture.oms_ai_summary ?? {}}
          onSelectEntity={selectEntity}
        />
      </div>
      <div class="panel grid-panel" class:active={tab === "assess"}>
        <AssessPanel {picture} bind:selectedEntityId onSelectEntity={selectEntity} />
      </div>
      <div class="panel fkcm-panel" class:active={tab === "killchain"}>
        <KillChainPanel {picture} bind:selectedEntityId bind:phaseFilter={killChainPhaseFilter} />
      </div>
    </div>
  </div>
</div>
