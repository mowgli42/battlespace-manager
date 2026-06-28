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
  import { entityPopupHtml, getOrCreateMilIcon } from "./lib/milSymbol.js";

  const MAP_ENTITY_CAP = 350;
  const TABS = [
    { id: "map", label: "Battlespace", key: "1" },
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
    platforms: [],
    fkcm_targets: [],
    track_history: {},
    threat_picture: {},
    fusion_rows: [],
    task_rows: [],
    mission_thread: {},
    entity_registry: [],
    feed_status: [],
    attention_queue: [],
    bda_items: [],
    advisor_suggestions: [],
    advisor_isr_assignments: [],
    timeline_view: {},
  });
  let markers = new Map();
  let cueLayers = [];
  let source = null;
  let map;
  let apiConnected = $state(false);
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
    else if (item.kind === "TARGET" || item.kind === "POPUP") {
      tab = "killchain";
      if (item.entity_id) selectedEntityId = item.entity_id;
    }
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
    for (const p of picture.platforms || []) {
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
  }

  function applyPayload(data) {
    picture = data;
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
      apiConnected = false;
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
    fetch("/api/picture")
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((data) => {
        apiConnected = true;
        applyPayload(data);
      })
      .catch(() => {
        apiConnected = false;
      });
  });

  onDestroy(() => {
    window.removeEventListener("keydown", onKey);
    source?.close();
    map?.remove();
  });

  $effect(() => {
    selectedEntityId;
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
    <span class="class-banner">UNCLASS // SIMULATION · Keys 1–7 tabs</span>
  </header>

  <MissionThreadBar {picture} onPhaseClick={onPhaseClick} />

  <nav class="tabs" aria-label="Main views">
    {#each TABS as t}
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
      <div class="panel" class:active={tab === "map"}>
        <div id="map"></div>
        <div class="narrative" class:narrative-warn={!apiConnected} role="status">{narrativeStatus()}</div>
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
        <TaskingPanel {picture} onSelectEntity={selectEntity} />
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
