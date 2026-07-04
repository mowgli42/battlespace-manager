<script>
  import { onMount, onDestroy } from "svelte";
  import L from "leaflet";
  import { bandLabel, conflictSeverityClass, conflictTypeLabel } from "./lib/rfFormat.js";

  let map;
  let source = null;
  let picture = $state({
    sim_minutes: 0,
    commlinks: { links: [], contacts: [] },
    emitters: [],
    ew_platforms: [],
    emcon_areas: [],
    spectrum: { rows: [], contested_bands: 0 },
    conflicts: [],
    deconfliction_summary: {},
  });

  let layers = $state({
    comms: true,
    emitters: true,
    jammers: true,
    emcon: true,
  });

  const mapLayers = {
    comms: new Map(),
    emitters: new Map(),
    jammers: new Map(),
    emcon: new Map(),
  };

  const summary = $derived(picture.deconfliction_summary || {});

  function linkStyle(link) {
    const contested = link.frequency_mhz && picture.conflicts.some(
      (c) => c.conflict_type === "jam_comm" && c.involved_ids?.includes(link.link_id)
    );
    return {
      color: contested ? "#f87171" : "#22d3ee",
      weight: contested ? 3 : 2,
      opacity: 0.85,
      dashArray: link.is_unavailable ? "8 6" : undefined,
    };
  }

  function updateMap() {
    if (!map) return;

    if (layers.comms) {
      const seen = new Set();
      for (const link of picture.commlinks?.links || []) {
        seen.add(link.link_id);
        const pts = (link.endpoints || []).map((e) => [e.lat, e.lon]);
        if (pts.length < 2) continue;
        const style = linkStyle(link);
        const tip = `${link.link_id} · ${link.band || link.subtype || link.type} · ${link.frequency_mhz || "?"} MHz`;
        if (mapLayers.comms.has(link.link_id)) {
          const layer = mapLayers.comms.get(link.link_id);
          layer.setLatLngs(pts);
          layer.setStyle(style);
          layer.setTooltipContent(tip);
        } else {
          const poly = L.polyline(pts, style).bindTooltip(tip, { sticky: true, className: "rf-tooltip" });
          poly.addTo(map);
          mapLayers.comms.set(link.link_id, poly);
        }
      }
      for (const [id, layer] of mapLayers.comms) {
        if (!seen.has(id)) {
          map.removeLayer(layer);
          mapLayers.comms.delete(id);
        }
      }
    } else {
      for (const [, layer] of mapLayers.comms) map.removeLayer(layer);
      mapLayers.comms.clear();
    }

    if (layers.emitters) {
      const seen = new Set();
      for (const em of picture.emitters || []) {
        if (em.latitude == null || em.longitude == null) continue;
        seen.add(em.emitter_id);
        const color = em.highlighted ? "#fef08a" : em.affiliation === "hostile" ? "#f87171" : "#34d399";
        const tip = `${em.label} · ${em.band || ""} · ${em.frequency_mhz || "?"} MHz${em.highlighted ? " · HIGHLIGHTED" : ""}`;
        if (mapLayers.emitters.has(em.emitter_id)) {
          const m = mapLayers.emitters.get(em.emitter_id);
          m.setLatLng([em.latitude, em.longitude]);
          m.setStyle({
            fillColor: color,
            color: em.highlighted ? "#fff" : color,
            weight: em.highlighted ? 3 : 2,
            radius: em.highlighted ? 11 : 7,
          });
          m.setTooltipContent(tip);
        } else {
          const m = L.circleMarker([em.latitude, em.longitude], {
            radius: em.highlighted ? 11 : 7,
            fillColor: color,
            color: em.highlighted ? "#fff" : color,
            weight: em.highlighted ? 3 : 2,
            fillOpacity: 0.9,
          }).bindTooltip(tip, { direction: "top", className: "rf-tooltip" });
          m.addTo(map);
          mapLayers.emitters.set(em.emitter_id, m);
        }
      }
      for (const [id, layer] of mapLayers.emitters) {
        if (!seen.has(id)) {
          map.removeLayer(layer);
          mapLayers.emitters.delete(id);
        }
      }
    } else {
      for (const [, layer] of mapLayers.emitters) map.removeLayer(layer);
      mapLayers.emitters.clear();
    }

    if (layers.jammers) {
      const seen = new Set();
      for (const jam of picture.ew_platforms || []) {
        if (jam.latitude == null || jam.longitude == null) continue;
        seen.add(jam.platform_id);
        const active = jam.jamming_active;
        const color = active ? "#f59e0b" : "#64748b";
        const radiusNm = jam.coverage_nm || 40;
        const tip = `${jam.callsign || jam.platform_id} · ${jam.band || ""} · ${active ? "JAMMING" : "standby"} · ${jam.coverage_nm ?? "?"} nm (FSPL)`;
        if (mapLayers.jammers.has(jam.platform_id)) {
          const group = mapLayers.jammers.get(jam.platform_id);
          group.marker.setLatLng([jam.latitude, jam.longitude]);
          group.circle.setLatLng([jam.latitude, jam.longitude]);
          group.circle.setStyle({ color, fillColor: color, fillOpacity: active ? 0.12 : 0.04 });
          group.marker.setTooltipContent(tip);
        } else {
          const marker = L.circleMarker([jam.latitude, jam.longitude], {
            radius: 8,
            fillColor: color,
            color,
            weight: 2,
            fillOpacity: 0.95,
          }).bindTooltip(tip, { direction: "top", className: "rf-tooltip" });
          const circle = L.circle([jam.latitude, jam.longitude], {
            radius: radiusNm * 1852,
            color,
            fillColor: color,
            weight: 1,
            fillOpacity: active ? 0.12 : 0.04,
            dashArray: active ? undefined : "6 8",
          });
          marker.addTo(map);
          circle.addTo(map);
          mapLayers.jammers.set(jam.platform_id, { marker, circle });
        }
      }
      for (const [id, group] of mapLayers.jammers) {
        if (!seen.has(id)) {
          map.removeLayer(group.marker);
          map.removeLayer(group.circle);
          mapLayers.jammers.delete(id);
        }
      }
    } else {
      for (const [, group] of mapLayers.jammers) {
        map.removeLayer(group.marker);
        map.removeLayer(group.circle);
      }
      mapLayers.jammers.clear();
    }

    if (layers.emcon) {
      const seen = new Set();
      for (const area of picture.emcon_areas || []) {
        seen.add(area.id);
        const latlngs = (area.polygon || []).map((p) => [p[0], p[1]]);
        const tip = `${area.name} · ${area.posture}`;
        if (mapLayers.emcon.has(area.id)) {
          const poly = mapLayers.emcon.get(area.id);
          poly.setLatLngs(latlngs);
          poly.setTooltipContent(tip);
        } else {
          const poly = L.polygon(latlngs, {
            color: "#a78bfa",
            fillColor: "#a78bfa",
            weight: 1,
            fillOpacity: 0.08,
            dashArray: "4 6",
          }).bindTooltip(tip, { sticky: true, className: "emcon-tooltip" });
          poly.addTo(map);
          mapLayers.emcon.set(area.id, poly);
        }
      }
      for (const [id, layer] of mapLayers.emcon) {
        if (!seen.has(id)) {
          map.removeLayer(layer);
          mapLayers.emcon.delete(id);
        }
      }
    } else {
      for (const [, layer] of mapLayers.emcon) map.removeLayer(layer);
      mapLayers.emcon.clear();
    }
  }

  $effect(() => {
    updateMap();
  });

  function applyPayload(data) {
    picture = data;
  }

  onMount(() => {
    map = L.map("rf-map", { zoomControl: true }).setView([28.2, 48.5], 7);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; CARTO",
      maxZoom: 18,
    }).addTo(map);

    source = new EventSource("/api/stream");
    source.onmessage = (ev) => {
      try {
        applyPayload(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };

    fetch("/api/picture")
      .then((r) => r.json())
      .then(applyPayload)
      .catch(() => {});
    applyHighlightFromUrl();
  });

  onDestroy(() => {
    source?.close();
    map?.remove();
  });

  function barHeight(row) {
    const base = 18;
    const extra = Math.min(54, (row.occupant_count || 1) * 10);
    return row.contested ? base + extra + 8 : base + extra;
  }

  function barColor(row) {
    if (row.jrfl_protected) return "#c4b5fd";
    if (row.contested) return "#f87171";
    if (row.emitter_classes?.includes("jammer")) return "#f59e0b";
    if (row.emitter_classes?.includes("radar")) return "#f87171";
    return "#22d3ee";
  }

  function applyHighlightFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const entityId = params.get("highlight");
    if (!entityId) return;
    fetch("/api/highlight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: entityId }),
    }).catch(() => {});
  }
</script>

<div class="rf-shell">
  <header class="rf-header">
    <h1>RF Spectrum · EMSO Deconfliction</h1>
    <span class="stat-pill">T+{Math.round(picture.sim_minutes)} min</span>
    <span class="stat-pill">Threat emitters <strong>{summary.threat_emitters ?? 0}</strong></span>
    <span class="stat-pill">Active jammers <strong>{summary.active_jammers ?? 0}</strong></span>
    <span class="stat-pill">Commlinks <strong>{picture.commlinks?.summary?.link_count ?? 0}</strong></span>
    <span class="stat-pill warn">Contested bands <strong>{summary.contested_bands ?? 0}</strong></span>
    <span class="stat-pill danger">Conflicts <strong>{summary.total_conflicts ?? 0}</strong></span>
    {#if picture.bus_connected}
      <span class="stat-pill">Redis bus <strong>live</strong></span>
    {/if}
  </header>

  <div class="rf-main">
    <div id="rf-map"></div>

    <aside class="rf-sidebar">
      <div class="layer-toggles">
        <label><input type="checkbox" bind:checked={layers.comms} /> Comms</label>
        <label><input type="checkbox" bind:checked={layers.emitters} /> Threat radars</label>
        <label><input type="checkbox" bind:checked={layers.jammers} /> EW / jamming</label>
        <label><input type="checkbox" bind:checked={layers.emcon} /> EMCON areas</label>
      </div>

      {#if picture.jrfl?.entries?.length}
        <div class="jrfl-panel">
          <h3>JRFL · {picture.jrfl.ea_authority?.level || "EACA"}</h3>
          <ul>
            {#each picture.jrfl.entries as entry (entry.id)}
              <li>
                <strong>{entry.label}</strong> · {entry.frequency_mhz} MHz
                <span class="badge">{entry.restriction}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <div class="conflict-list">
        {#if picture.conflicts.length === 0}
          <div class="empty-state">No RF conflicts detected.</div>
        {:else}
          {#each picture.conflicts as conflict (conflict.conflict_id)}
            <article class="conflict-card">
              <h3>{conflict.summary}</h3>
              <p>{conflict.recommendation.replaceAll("_", " ")}</p>
              <div class="conflict-meta">
                <span class="badge {conflictSeverityClass(conflict.severity)}">{conflict.severity}</span>
                <span class="badge">{conflictTypeLabel(conflict.conflict_type)}</span>
                {#if conflict.frequency_mhz}
                  <span class="badge">{conflict.frequency_mhz} MHz</span>
                {/if}
              </div>
            </article>
          {/each}
        {/if}
      </div>
    </aside>
  </div>

  <section class="rf-spectrum">
    <h2>Frequency occupancy · JRFL protected (violet) · contested (red)</h2>
    <div class="spectrum-bars">
      {#each picture.spectrum?.rows || [] as row (row.frequency_mhz)}
        <div>
          <div
            class="spectrum-bar"
            class:contested={row.contested}
            class:jrfl={row.jrfl_protected}
            style="height: {barHeight(row)}px; background: {barColor(row)}"
            title="{row.occupants?.join(', ')}"
          ></div>
          <div class="spectrum-bar-label">{row.frequency_mhz}<br />{bandLabel(row.frequency_mhz)}</div>
        </div>
      {/each}
    </div>
  </section>
</div>
