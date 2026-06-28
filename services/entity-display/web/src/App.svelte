<script>
  import { onMount, onDestroy } from "svelte";
  import L from "leaflet";

  let map;
  let markers = new Map();
  let linkLayers = new Map();
  let contactMarkers = new Map();
  let billingBadges = new Map();

  let tracks = $state([]);
  let commlinks = $state({ contacts: [], links: [], reservations: [], summary: {} });
  let stats = $state({ total: 0, by_category: {}, alerts: 0, commlinks: {} });
  let alertText = $state("");
  let showToast = $state(false);
  let source = null;

  const categoryColors = {
    "High-Altitude-Commercial": "#00d4ff",
    "Mid-Altitude-Commercial": "#7dd3fc",
    "Low-Altitude": "#fbbf24",
    Uncategorized: "#94a3b8",
  };

  function colorFor(track) {
    if (track.threat_level === "High" || ["7700", "7500", "7600"].includes(track.squawk)) {
      return "#ff4b4b";
    }
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

  function updateMarkers(nextTracks) {
    const seen = new Set();
    for (const t of nextTracks) {
      seen.add(t.track_id);
      const color = colorFor(t);
      if (markers.has(t.track_id)) {
        const m = markers.get(t.track_id);
        m.setLatLng([t.latitude, t.longitude]);
        m.setStyle({ fillColor: color, color });
      } else {
        const m = L.circleMarker([t.latitude, t.longitude], {
          radius: 5,
          fillColor: color,
          color,
          weight: 1,
          fillOpacity: 0.9,
        }).bindTooltip(`${t.callsign} · ${Math.round(t.altitude_feet)} ft`, {
          direction: "top",
        });
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
      stats = await res.json();
    } catch (e) {
      console.warn("stats fetch failed", e);
    }
  }

  function applyPayload(data) {
    tracks = data.tracks || [];
    updateMarkers(tracks);
    if (data.commlinks) {
      updateCommlinks(data.commlinks);
    }
    const alertTrack = tracks.find(
      (t) => t.threat_level === "High" || ["7700", "7500", "7600"].includes(t.squawk)
    );
    if (alertTrack) {
      alertText = `Emergency: ${alertTrack.callsign} (squawk ${alertTrack.squawk})`;
      showToast = true;
    } else {
      showToast = false;
    }
  }

  function connectStream() {
    source = new EventSource("/api/stream");
    source.onmessage = (ev) => {
      try {
        applyPayload(JSON.parse(ev.data));
      } catch (e) {
        console.warn("bad sse payload", e);
      }
    };
    source.onerror = () => {
      source?.close();
      setTimeout(connectStream, 2000);
    };
  }

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
    <div class="top-row">
      <div class="glass">
        <h2>Active tracks</h2>
        <div class="row"><span>Total</span><strong>{stats.total || tracks.length}</strong></div>
        <div class="row"><span>Alerts</span><strong>{stats.alerts}</strong></div>
      </div>
      <div class="glass">
        <h2>By category</h2>
        {#each Object.entries(stats.by_category || {}) as [cat, count]}
          <div class="row"><span>{cat}</span><span>{count}</span></div>
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
        <div class="legend">
          <span class="legend-item"><i class="swatch active"></i> Active</span>
          <span class="legend-item"><i class="swatch metered"></i> Metered</span>
          <span class="legend-item"><i class="swatch unavailable"></i> Unavailable</span>
        </div>
      </div>
    </div>
  </div>
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
  <footer>o-my · UCI XML · Redis pub/sub</footer>
</div>
