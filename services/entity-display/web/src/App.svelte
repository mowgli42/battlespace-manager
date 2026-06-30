<script>
  import { onMount, onDestroy } from "svelte";
  import L from "leaflet";
  import { filterTracks, trackAffiliation, isMoving } from "./lib/trackFilters.js";

  let map;
  let markers = new Map();
  let linkLayers = new Map();
  let contactMarkers = new Map();
  let billingBadges = new Map();

  let allTracks = $state([]);
  let commlinks = $state({ contacts: [], links: [], reservations: [], summary: {} });
  let feedStatus = $state([]);
  let stats = $state({ total: 0, by_category: {}, by_affiliation: {}, alerts: 0, commlinks: {} });
  let alertText = $state("");
  let showToast = $state(false);
  let source = null;
  let apiConnected = $state(false);

  let selectedTrackId = $state(null);
  let feedPanelOpen = $state(false);
  let filters = $state({
    affiliation: "all",
    kinematic: "all",
    entityType: "all",
    taggedOnly: false,
  });

  const OPERATOR_TAGS = ["WATCH", "PROMOTE", "TASK", "ISR", "HOLD"];

  const categoryColors = {
    "High-Altitude-Commercial": "#00d4ff",
    "Mid-Altitude-Commercial": "#7dd3fc",
    "Low-Altitude": "#fbbf24",
    Uncategorized: "#94a3b8",
  };

  let visibleTracks = $derived(filterTracks(allTracks, filters));
  let selectedTrack = $derived(allTracks.find((t) => t.track_id === selectedTrackId) || null);

  function colorFor(track) {
    if (track.promoted) return "#f472b6";
    if (track.threat_level === "High" || ["7700", "7500", "7600"].includes(track.squawk)) {
      return "#ff4b4b";
    }
    const aff = track.affiliation || trackAffiliation(track);
    if (aff === "hostile") return "#ff6b6b";
    if (aff === "friendly") return "#34d399";
    return categoryColors[track.primary_category] || categoryColors.Uncategorized;
  }

  function linkColor(link) {
    if (link.is_unavailable) return "#ff4b4b";
    if (link.is_degraded) return "#fbbf24";
    if (link.is_metered) return "#f59e0b";
    return "#22d3ee";
  }

  function linkStyle(link) {
    return {
      color: linkColor(link),
      weight: link.is_metered ? 4 : 2,
      opacity: link.is_unavailable ? 0.45 : 0.9,
      dashArray: link.is_unavailable ? "10 8" : undefined,
    };
  }

  function linkTooltip(link) {
    const cost =
      link.estimated_cost > 0
        ? ` · $${link.estimated_cost.toFixed(2)} ${link.currency}`
        : "";
    const resv =
      link.reservation_status && link.reservation_status !== "none"
        ? ` · resv ${link.reservation_status}`
        : "";
    return `${link.link_id} · ${link.type}/${link.subtype} · ${link.status} · ${link.billing_label}${resv}${cost}`;
  }

  function midpoint(endpoints) {
    if (!endpoints.length) return null;
    const lat = endpoints.reduce((s, e) => s + e.lat, 0) / endpoints.length;
    const lon = endpoints.reduce((s, e) => s + e.lon, 0) / endpoints.length;
    return [lat, lon];
  }

  function trackTooltip(t) {
    const aff = t.affiliation || trackAffiliation(t);
    const kin = isMoving(t) ? "moving" : "static";
    const tags = [...(t.tags || []), ...(t.operator_tags || [])].slice(0, 6).join(", ");
    return `${t.callsign} · ${Math.round(t.altitude_feet)} ft · ${aff} · ${kin}${tags ? " · " + tags : ""}`;
  }

  function selectTrack(id) {
    selectedTrackId = selectedTrackId === id ? null : id;
    updateMarkers(visibleTracks);
    const t = allTracks.find((x) => x.track_id === id);
    if (t && map) map.panTo([t.latitude, t.longitude], { animate: true });
  }

  function updateMarkers(nextTracks) {
    if (!map) return;
    const seen = new Set();
    for (const t of nextTracks) {
      seen.add(t.track_id);
      const color = colorFor(t);
      const selected = selectedTrackId === t.track_id;
      const radius = selected ? 8 : t.promoted ? 7 : 5;
      if (markers.has(t.track_id)) {
        const m = markers.get(t.track_id);
        m.setLatLng([t.latitude, t.longitude]);
        m.setStyle({
          fillColor: color,
          color: selected ? "#fff" : color,
          weight: selected ? 2 : 1,
          radius,
        });
        m.setTooltipContent(trackTooltip(t));
      } else {
        const m = L.circleMarker([t.latitude, t.longitude], {
          radius,
          fillColor: color,
          color: selected ? "#fff" : color,
          weight: selected ? 2 : 1,
          fillOpacity: 0.9,
        })
          .bindTooltip(trackTooltip(t), { direction: "top" })
          .on("click", () => selectTrack(t.track_id));
        m.addTo(map);
        markers.set(t.track_id, m);
      }
    }
    for (const [id, m] of markers) {
      if (!seen.has(id)) {
        map.removeLayer(m);
        markers.delete(id);
      }
    }
  }

  function updateCommlinks(display) {
    if (!display || !map) return;
    commlinks = display;

    const seenLinks = new Set();
    for (const link of display.links || []) {
      seenLinks.add(link.link_id);
      const pts = (link.endpoints || []).map((e) => [e.lat, e.lon]);
      const style = linkStyle(link);

      if (pts.length >= 2) {
        if (linkLayers.has(link.link_id)) {
          const layer = linkLayers.get(link.link_id);
          layer.setLatLngs(pts);
          layer.setStyle(style);
          layer.setTooltipContent(linkTooltip(link));
        } else {
          const poly = L.polyline(pts, style).bindTooltip(linkTooltip(link), {
            sticky: true,
            className: "commlink-tooltip",
          });
          poly.addTo(map);
          linkLayers.set(link.link_id, poly);
        }
      } else if (linkLayers.has(link.link_id)) {
        map.removeLayer(linkLayers.get(link.link_id));
        linkLayers.delete(link.link_id);
      }

      const center = midpoint(link.endpoints || []);
      if (center && (link.is_metered || link.reservation_status === "active")) {
        const label = link.is_metered ? link.billing_label : "RESV";
        const cls = link.is_metered ? "billing-badge metered" : "billing-badge reserved";
        if (billingBadges.has(link.link_id)) {
          const icon = billingBadges.get(link.link_id);
          icon.setLatLng(center);
          icon.setIcon(L.divIcon({ className: cls, html: label, iconSize: [0, 0] }));
        } else {
          const icon = L.marker(center, {
            icon: L.divIcon({ className: cls, html: label, iconSize: [0, 0] }),
            interactive: false,
          });
          icon.addTo(map);
          billingBadges.set(link.link_id, icon);
        }
      } else if (billingBadges.has(link.link_id)) {
        map.removeLayer(billingBadges.get(link.link_id));
        billingBadges.delete(link.link_id);
      }
    }

    for (const [id, layer] of linkLayers) {
      if (!seenLinks.has(id)) {
        map.removeLayer(layer);
        linkLayers.delete(id);
      }
    }
    for (const [id, badge] of billingBadges) {
      if (!seenLinks.has(id)) {
        map.removeLayer(badge);
        billingBadges.delete(id);
      }
    }

    const seenContacts = new Set();
    for (const contact of display.contacts || []) {
      seenContacts.add(contact.id);
      const tooltip = `${contact.name} · ${contact.platform}`;
      if (contactMarkers.has(contact.id)) {
        const m = contactMarkers.get(contact.id);
        m.setLatLng([contact.lat, contact.lon]);
      } else {
        const m = L.circleMarker([contact.lat, contact.lon], {
          radius: 4,
          fillColor: "#a78bfa",
          color: "#c4b5fd",
          weight: 1,
          fillOpacity: 0.85,
        }).bindTooltip(tooltip, { direction: "bottom" });
        m.addTo(map);
        contactMarkers.set(contact.id, m);
      }
    }
    for (const [id, m] of contactMarkers) {
      if (!seenContacts.has(id)) {
        map.removeLayer(m);
        contactMarkers.delete(id);
      }
    }
  }

  async function loadStats() {
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();
      stats = data;
      if (data.feed_status) feedStatus = data.feed_status;
    } catch (e) {
      console.warn("stats fetch failed", e);
    }
  }

  function applyPayload(data) {
    allTracks = data.tracks || [];
    if (data.feed_status) feedStatus = data.feed_status;
    updateMarkers(visibleTracks);
    if (data.commlinks) updateCommlinks(data.commlinks);
    const alertTrack = allTracks.find(
      (t) => t.threat_level === "High" || ["7700", "7500", "7600"].includes(t.squawk)
    );
    if (alertTrack) {
      alertText = `Emergency: ${alertTrack.callsign} (squawk ${alertTrack.squawk})`;
      showToast = true;
    } else {
      showToast = false;
    }
  }

  async function addOperatorTag(tag) {
    if (!selectedTrackId) return;
    try {
      const res = await fetch(`/api/tracks/${selectedTrackId}/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag }),
      });
      if (res.ok) {
        const data = await res.json();
        allTracks = allTracks.map((t) => (t.track_id === data.track.track_id ? data.track : t));
        updateMarkers(visibleTracks);
      }
    } catch (e) {
      console.warn(e);
    }
  }

  async function togglePromote() {
    if (!selectedTrackId) return;
    try {
      const res = await fetch(`/api/tracks/${selectedTrackId}/promote`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        allTracks = allTracks.map((t) => (t.track_id === data.track.track_id ? data.track : t));
        updateMarkers(visibleTracks);
      }
    } catch (e) {
      console.warn(e);
    }
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
        console.warn("bad sse payload", e);
      }
    };
    source.onerror = () => {
      apiConnected = false;
      source?.close();
      setTimeout(connectStream, 2000);
    };
  }

  function setFilter(key, value) {
    filters = { ...filters, [key]: value };
    updateMarkers(filterTracks(allTracks, filters));
  }

  function feedStatusLabel(f) {
    if (f.status === "live") return "Live";
    if (f.status === "stale") return `Stale ${f.last_seen_age_s}s`;
    return "Idle";
  }

  $effect(() => {
    visibleTracks;
    filters;
    selectedTrackId;
    if (map) updateMarkers(filterTracks(allTracks, filters));
  });

  onMount(() => {
    map = L.map("map", { zoomControl: false }).setView([34.05, -118.2], 7);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> CARTO',
      maxZoom: 19,
    }).addTo(map);
    connectStream();
    loadStats();
    const statsTimer = setInterval(loadStats, 5000);
    return () => clearInterval(statsTimer);
  });

  onDestroy(() => {
    source?.close();
    map?.remove();
  });
</script>

<div class="layout">
  <div id="map"></div>

  <div class="hud">
    <div class="filter-bar glass">
      <div class="filter-group">
        <span class="filter-label">Affiliation</span>
        <div class="filter-chips" role="group" aria-label="Affiliation filter">
          {#each [
            { id: "all", label: "All" },
            { id: "friendly", label: "Friendly" },
            { id: "hostile", label: "Hostile" },
            { id: "unknown", label: "Unknown" },
          ] as f}
            <button
              type="button"
              class:active={filters.affiliation === f.id}
              onclick={() => setFilter("affiliation", f.id)}
            >{f.label}</button>
          {/each}
        </div>
      </div>
      <div class="filter-group">
        <span class="filter-label">Kinematic</span>
        <div class="filter-chips" role="group" aria-label="Kinematic filter">
          {#each [
            { id: "all", label: "All" },
            { id: "moving", label: "Moving" },
            { id: "static", label: "Static" },
          ] as f}
            <button
              type="button"
              class:active={filters.kinematic === f.id}
              onclick={() => setFilter("kinematic", f.id)}
            >{f.label}</button>
          {/each}
        </div>
      </div>
      <div class="filter-group">
        <span class="filter-label">Type</span>
        <div class="filter-chips" role="group" aria-label="Entity type filter">
          {#each [
            { id: "all", label: "All" },
            { id: "aircraft", label: "Aircraft" },
          ] as f}
            <button
              type="button"
              class:active={filters.entityType === f.id}
              onclick={() => setFilter("entityType", f.id)}
            >{f.label}</button>
          {/each}
        </div>
      </div>
      <button
        type="button"
        class="filter-chip-toggle"
        class:active={filters.taggedOnly}
        onclick={() => setFilter("taggedOnly", !filters.taggedOnly)}
      >Tagged / promoted only</button>
      <div class="filter-count">{visibleTracks.length} / {allTracks.length} on map</div>
    </div>

    <div class="top-row">
      <div class="glass feed-panel-wrap">
        <button
          type="button"
          class="feed-toggle"
          aria-expanded={feedPanelOpen}
          onclick={() => (feedPanelOpen = !feedPanelOpen)}
        >
          <span class="live-dot" class:live={apiConnected}></span>
          <span>Live feeds</span>
          <span class="feed-summary">{feedStatus.filter((f) => f.active).length}/{feedStatus.length} live</span>
          <span class="chevron" class:open={feedPanelOpen}>▾</span>
        </button>
        {#if feedPanelOpen}
          <div class="feed-dropdown" role="list">
            {#each feedStatus as feed}
              <div class="feed-row" class:feed-live={feed.active} role="listitem">
                <div class="feed-head">
                  <span class="feed-id">{feed.feed_id}</span>
                  <span class="feed-status status-{feed.status}">{feedStatusLabel(feed)}</span>
                </div>
                <div class="feed-meta">
                  <span>{feed.label}</span>
                  <span>{feed.type}</span>
                  {#if feed.message_count}<span>{feed.message_count} msgs</span>{/if}
                </div>
              </div>
            {:else}
              <p class="badge">Waiting for bus traffic…</p>
            {/each}
          </div>
        {/if}
      </div>

      <div class="glass">
        <h2>Active tracks</h2>
        <div class="row"><span>Visible</span><strong>{visibleTracks.length}</strong></div>
        <div class="row"><span>Total</span><strong>{stats.total || allTracks.length}</strong></div>
        <div class="row"><span>Alerts</span><strong>{stats.alerts}</strong></div>
        <div class="row"><span>Promoted</span><strong>{stats.promoted ?? 0}</strong></div>
      </div>

      <div class="glass">
        <h2>By affiliation</h2>
        {#each Object.entries(stats.by_affiliation || {}) as [aff, count]}
          <div class="row"><span>{aff}</span><span>{count}</span></div>
        {:else}
          <p class="badge">Waiting for sorter…</p>
        {/each}
      </div>

      <div class="glass commlink-panel">
        <h2>Commlinks</h2>
        <div class="row">
          <span>Active</span>
          <strong>{stats.commlinks?.active ?? commlinks.summary?.active_links ?? 0}/{stats.commlinks?.total ?? commlinks.summary?.link_count ?? 0}</strong>
        </div>
        <div class="row">
          <span>Metered</span>
          <strong class="metered">{stats.commlinks?.metered ?? commlinks.summary?.metered_links ?? 0}</strong>
        </div>
        <div class="row">
          <span>Unavailable</span>
          <strong class="unavailable">{stats.commlinks?.unavailable ?? commlinks.summary?.unavailable_links ?? 0}</strong>
        </div>
      </div>
    </div>
  </div>

  {#if selectedTrack}
    <div class="entity-panel glass">
      <div class="entity-head">
        <h2>{selectedTrack.callsign}</h2>
        <button type="button" class="close-btn" onclick={() => (selectedTrackId = null)} aria-label="Close">×</button>
      </div>
      <div class="entity-meta">
        <span>{selectedTrack.affiliation || trackAffiliation(selectedTrack)}</span>
        <span>{isMoving(selectedTrack) ? "Moving" : "Static"}</span>
        <span>{Math.round(selectedTrack.altitude_feet)} ft</span>
        <span>GS {Math.round(selectedTrack.ground_speed_kts)} kts</span>
        <span>SQ {selectedTrack.squawk}</span>
      </div>
      {#if selectedTrack.primary_category}
        <p class="entity-cat">{selectedTrack.primary_category} · {selectedTrack.sub_category || "—"}</p>
      {/if}
      <div class="tag-section">
        <span class="tag-label">Sorter tags</span>
        <div class="tag-row">
          {#each selectedTrack.tags || [] as tag}
            <span class="tag chip-sorter">{tag}</span>
          {:else}
            <span class="badge">None</span>
          {/each}
        </div>
      </div>
      <div class="tag-section">
        <span class="tag-label">Operator tags</span>
        <div class="tag-row">
          {#each selectedTrack.operator_tags || [] as tag}
            <span class="tag chip-operator">{tag}</span>
          {:else}
            <span class="badge">None — add below</span>
          {/each}
        </div>
        <div class="action-chips">
          {#each OPERATOR_TAGS as tag}
            <button
              type="button"
              class="action-chip"
              class:active={selectedTrack.operator_tags?.includes(tag)}
              onclick={() => addOperatorTag(tag)}
            >{tag}</button>
          {/each}
        </div>
      </div>
      <button
        type="button"
        class="promote-btn"
        class:active={selectedTrack.promoted}
        onclick={togglePromote}
      >
        {selectedTrack.promoted ? "✓ Promoted for action" : "Promote for action"}
      </button>
    </div>
  {/if}

  <div class="reservation-panel glass">
    <h2>Reservations</h2>
    {#each commlinks.reservations || [] as resv}
      <div class="reservation-row">
        <div class="reservation-head">
          <span class="reservation-id">{resv.reservation_id}</span>
          <span class="reservation-status status-{resv.status}">{resv.status}</span>
        </div>
        <div class="reservation-meta">
          {#if resv.link_id}<span>{resv.link_id}</span>{/if}
          <span>{resv.priority}</span>
        </div>
        <p class="reservation-mission">{resv.mission}</p>
      </div>
    {:else}
      <p class="badge">Waiting for commlink-status…</p>
    {/each}
  </div>

  <div class="toast" class:visible={showToast}>{alertText}</div>
  <footer>o-my · UCI XML · Redis pub/sub · click track to tag / promote</footer>
</div>
