<script>
  import {
    anyLiveService,
    liveServiceCount,
    statusClass,
    statusLabel,
  } from "./lib/omsAiServices.js";

  let {
    suggestions = [],
    omsAiServices = [],
    omsAiSummary = {},
    onAccept = async () => {},
    onSelectEntity = () => {},
  } = $props();

  let busy = $state(null);
  let error = $state("");

  const SHORT_LABELS = {
    "mission-advisor": "Advisor",
    "entity-sorter": "Sorter",
    "task-allocator": "Allocator",
    "embedded-advisor": "Advisor",
  };

  let servicesLive = $derived(anyLiveService(omsAiServices));
  let openSuggestions = $derived(
    (suggestions || []).filter((s) => s.status !== "accepted" && s.status !== "dismissed")
  );

  let orderedServices = $derived.by(() => {
    const preferred = ["mission-advisor", "entity-sorter", "task-allocator"];
    const byId = Object.fromEntries((omsAiServices || []).map((s) => [s.service_id, s]));
    const ordered = preferred.map((id) => byId[id]).filter(Boolean);
    for (const svc of omsAiServices || []) {
      if (!preferred.includes(svc.service_id)) ordered.push(svc);
    }
    return ordered;
  });

  function shortLabel(svc) {
    return SHORT_LABELS[svc.service_id] || svc.label || svc.service_id;
  }

  async function post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.message || data.detail || "Request failed");
    return data;
  }

  async function accept(sug) {
    if (sug.status === "accepted") return;
    busy = sug.suggestion_id;
    error = "";
    try {
      const data = await post("/api/advisor/accept", { suggestion_id: sug.suggestion_id });
      await onAccept(data);
    } catch (e) {
      error = e.message || String(e);
    } finally {
      busy = null;
    }
  }

  async function dismiss(sug) {
    busy = sug.suggestion_id;
    error = "";
    try {
      await post("/api/advisor/dismiss", { suggestion_id: sug.suggestion_id });
    } catch (e) {
      error = e.message || String(e);
    } finally {
      busy = null;
    }
  }

  async function snooze(sug, minutes = 15) {
    busy = sug.suggestion_id;
    error = "";
    try {
      await post("/api/advisor/snooze", { suggestion_id: sug.suggestion_id, minutes });
    } catch (e) {
      error = e.message || String(e);
    } finally {
      busy = null;
    }
  }
</script>

<section class="advisor-panel" aria-label="OMS AI recommendations">
  <div class="oms-bar" role="list" aria-label="OMS AI services">
    <span class="oms-label">OMS AI</span>
    {#each orderedServices as svc (svc.service_id)}
      <div
        class="oms-chip"
        class:live={svc.status === "live"}
        role="listitem"
        title={svc.label || svc.service_id}
      >
        <span class="status-dot" class:live={svc.status === "live"} class:degraded={svc.status === "degraded"}></span>
        <span class="chip-name">{shortLabel(svc)}</span>
        <span class="status-pill {statusClass(svc.status)}">{statusLabel(svc.status)}</span>
      </div>
    {:else}
      <span class="empty">No services</span>
    {/each}
    {#if liveServiceCount(omsAiSummary)}
      <span class="live-count">{liveServiceCount(omsAiSummary)} live</span>
    {/if}
  </div>

  {#if error}
    <p class="err" role="alert">{error}</p>
  {/if}

  {#if servicesLive && openSuggestions.length}
    <ul class="rec-list">
      {#each openSuggestions as sug (sug.suggestion_id)}
        <li class="sug-card">
          <div class="meta">
            <span class="role">{sug.suggested_role}</span>
            <span class="pri">P{sug.priority}</span>
            {#if sug.source_service}
              <span class="src">{sug.source_service}</span>
            {/if}
          </div>
          <button type="button" class="target" onclick={() => onSelectEntity(sug.target_entity_id)}>
            {sug.target_name || sug.target_entity_id}
          </button>
          <p class="reason">{sug.reason}</p>
          <div class="actions">
            <button
              type="button"
              class="accept"
              disabled={busy === sug.suggestion_id}
              onclick={() => accept(sug)}
            >
              {busy === sug.suggestion_id ? "Working…" : "Accept → Task"}
            </button>
            <button
              type="button"
              class="secondary"
              disabled={busy === sug.suggestion_id}
              onclick={() => snooze(sug, 15)}
            >
              Snooze 15m
            </button>
            <button
              type="button"
              class="secondary dismiss"
              disabled={busy === sug.suggestion_id}
              onclick={() => dismiss(sug)}
            >
              Dismiss
            </button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}

  {#each suggestions.filter((s) => s.status === "accepted") as sug (sug.suggestion_id)}
    <p class="accepted">Accepted {sug.suggested_role} on {sug.target_entity_id}</p>
  {/each}
</section>

<style>
  .advisor-panel {
    border-bottom: 1px solid var(--glass-border);
    padding: 6px 12px;
    background: rgba(88, 28, 135, 0.08);
  }
  .oms-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    min-height: 28px;
  }
  .oms-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #c4b5fd;
    margin-right: 2px;
    flex-shrink: 0;
  }
  .oms-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid rgba(100, 116, 139, 0.4);
    background: rgba(15, 10, 30, 0.45);
    font-size: 11px;
  }
  .oms-chip.live {
    border-color: rgba(52, 211, 153, 0.5);
  }
  .chip-name {
    color: var(--text-primary);
    font-weight: 600;
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #64748b;
    flex-shrink: 0;
  }
  .status-dot.live {
    background: #34d399;
  }
  .status-dot.degraded {
    background: #fbbf24;
  }
  .status-pill {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 1px 5px;
    border-radius: 4px;
  }
  .status-pill.live {
    background: rgba(52, 211, 153, 0.2);
    color: #6ee7b7;
  }
  .status-pill.degraded {
    background: rgba(251, 191, 36, 0.2);
    color: #fcd34d;
  }
  .status-pill.offline {
    background: rgba(100, 116, 139, 0.25);
    color: #94a3b8;
  }
  .live-count {
    margin-left: auto;
    font-size: 10px;
    color: #6ee7b7;
  }
  .rec-list {
    list-style: none;
    margin: 8px 0 0;
    padding: 0;
  }
  .sug-card {
    padding: 10px;
    margin-bottom: 8px;
    border-radius: 8px;
    border: 1px solid rgba(167, 139, 250, 0.35);
    background: rgba(15, 10, 30, 0.6);
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .role {
    font-size: 10px;
    font-weight: 700;
    color: #a78bfa;
  }
  .pri,
  .src {
    font-size: 10px;
    color: var(--text-muted);
  }
  .src {
    margin-left: auto;
    font-family: ui-monospace, monospace;
  }
  .target {
    background: none;
    border: none;
    color: var(--accent);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    padding: 0;
    text-align: left;
  }
  .reason {
    font-size: 11px;
    color: var(--text-muted);
    margin: 6px 0;
    line-height: 1.35;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .accept {
    flex: 1 1 100%;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid #7c3aed;
    background: rgba(124, 58, 237, 0.35);
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
  }
  .secondary {
    flex: 1;
    padding: 5px 8px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(30, 20, 50, 0.5);
    color: var(--text-muted);
    font-size: 10px;
    cursor: pointer;
  }
  .secondary.dismiss {
    color: #fca5a5;
    border-color: rgba(248, 113, 113, 0.4);
  }
  .accept:disabled,
  .secondary:disabled {
    opacity: 0.6;
  }
  .empty,
  .accepted {
    font-size: 11px;
    color: var(--text-muted);
  }
  .err {
    color: var(--danger);
    font-size: 11px;
  }
</style>
