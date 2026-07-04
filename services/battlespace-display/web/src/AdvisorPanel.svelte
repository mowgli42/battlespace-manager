<script>
  import {
    anyLiveService,
    formatScopes,
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
    <h2>OMS AI Services</h2>
    <p class="hint">
      Recommendations appear only when an OMS AI service is live
      {#if liveServiceCount(omsAiSummary)}
        · {liveServiceCount(omsAiSummary)} live
      {/if}
    </p>
  </header>

  <div class="service-grid" role="list" aria-label="OMS AI service status">
    {#each omsAiServices as svc (svc.service_id)}
      <div class="service-row" class:live={svc.status === "live"} role="listitem">
        <div class="service-head">
          <span class="status-dot" class:live={svc.status === "live"} class:degraded={svc.status === "degraded"}></span>
          <strong>{svc.label}</strong>
          <span class="status-pill {statusClass(svc.status)}">{statusLabel(svc.status)}</span>
        </div>
        <p class="service-scopes">{formatScopes(svc.scopes)}</p>
        {#if svc.open_recommendation_count > 0}
          <p class="service-recs">{svc.open_recommendation_count} open recommendation{svc.open_recommendation_count === 1 ? "" : "s"}</p>
        {/if}
        {#if svc.isr_assignment_count > 0}
          <p class="service-recs">{svc.isr_assignment_count} ISR assignment{svc.isr_assignment_count === 1 ? "" : "s"}</p>
        {/if}
        {#if svc.detail}
          <p class="service-detail">{svc.detail}</p>
        {/if}
      </div>
    {:else}
      <p class="empty">No OMS AI services registered</p>
    {/each}
  </div>

  {#if error}
    <p class="err" role="alert">{error}</p>
  {/if}

  {#if servicesLive}
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
      {:else}
        <li class="empty">No open recommendations from live OMS AI services</li>
      {/each}
    </ul>
  {:else}
    <p class="offline-msg">
      Start <code>mission-advisor</code> (:8005) or set <code>ADVISOR_EMBEDDED=1</code> for local dev.
    </p>
  {/if}

  {#each suggestions.filter((s) => s.status === "accepted") as sug (sug.suggestion_id)}
    <p class="accepted">✓ Accepted {sug.suggested_role} on {sug.target_entity_id}</p>
  {/each}
</section>

<style>
  .advisor-panel {
    border-bottom: 1px solid var(--glass-border);
    padding: 12px 14px;
    max-height: 360px;
    overflow-y: auto;
    background: rgba(88, 28, 135, 0.12);
  }
  header h2 {
    margin: 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #c4b5fd;
  }
  .hint {
    margin: 4px 0 10px;
    font-size: 10px;
    color: var(--text-muted);
  }
  .service-grid {
    display: grid;
    gap: 8px;
    margin-bottom: 12px;
  }
  .service-row {
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid rgba(100, 116, 139, 0.35);
    background: rgba(15, 10, 30, 0.45);
    font-size: 11px;
  }
  .service-row.live {
    border-color: rgba(52, 211, 153, 0.45);
  }
  .service-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #64748b;
  }
  .status-dot.live {
    background: #34d399;
  }
  .status-dot.degraded {
    background: #fbbf24;
  }
  .status-pill {
    margin-left: auto;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 6px;
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
  .service-scopes {
    margin: 0;
    color: #a78bfa;
    font-size: 10px;
  }
  .service-recs {
    margin: 4px 0 0;
    color: #c4b5fd;
    font-size: 10px;
  }
  .service-detail {
    margin: 4px 0 0;
    color: var(--text-muted);
    font-size: 9px;
  }
  .rec-heading {
    margin: 0 0 8px;
    font-size: 10px;
    text-transform: uppercase;
    color: #c4b5fd;
  }
  .offline-msg {
    font-size: 11px;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.4;
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
