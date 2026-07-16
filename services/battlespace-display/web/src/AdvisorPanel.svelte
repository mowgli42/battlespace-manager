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

  let servicesLive = $derived(anyLiveService(omsAiServices));
  let openSuggestions = $derived(
    (suggestions || []).filter((s) => s.status !== "accepted" && s.status !== "dismissed")
  );

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
  <header>
    <h2>OMS AI</h2>
    {#if liveServiceCount(omsAiSummary)}
      <span class="live-count">{liveServiceCount(omsAiSummary)} live</span>
    {/if}
  </header>

  <div class="service-lines" role="list" aria-label="OMS AI service status">
    {#each omsAiServices as svc (svc.service_id)}
      <div class="service-line" class:live={svc.status === "live"} role="listitem">
        <span class="status-dot" class:live={svc.status === "live"} class:degraded={svc.status === "degraded"}></span>
        <span class="svc-name">{svc.label}</span>
        <span class="status-pill {statusClass(svc.status)}">{statusLabel(svc.status)}</span>
      </div>
    {:else}
      <p class="empty">No OMS AI services registered</p>
    {/each}
  </div>

  {#if error}
    <p class="err" role="alert">{error}</p>
  {/if}

  {#if servicesLive && openSuggestions.length}
    <h3 class="rec-heading">Recommendations</h3>
    <ul>
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
    padding: 8px 14px;
    max-height: 220px;
    overflow-y: auto;
    background: rgba(88, 28, 135, 0.1);
  }
  header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 6px;
  }
  header h2 {
    margin: 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #c4b5fd;
  }
  .live-count {
    font-size: 10px;
    color: #6ee7b7;
  }
  .service-lines {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .service-line {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 22px;
    padding: 2px 0;
    font-size: 11px;
  }
  .svc-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-primary);
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
    letter-spacing: 0.06em;
    padding: 1px 6px;
    border-radius: 4px;
    flex-shrink: 0;
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
  .rec-heading {
    margin: 10px 0 8px;
    font-size: 10px;
    text-transform: uppercase;
    color: #c4b5fd;
  }
  ul {
    list-style: none;
    margin: 0;
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
