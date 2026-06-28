<script>
  let { suggestions = [], onAccept = async () => {}, onSelectEntity = () => {} } = $props();

  let busy = $state(null);
  let error = $state("");

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

<section class="advisor-panel" aria-label="AI mission advisor">
  <header>
    <h2>AI Advisor</h2>
    <p class="hint">Strike suggestions require approval · ISR auto-tasked on bus</p>
  </header>
  {#if error}
    <p class="err" role="alert">{error}</p>
  {/if}
  <ul>
    {#each suggestions as sug (sug.suggestion_id)}
      <li class="sug-card">
        <div class="meta">
          <span class="role">{sug.suggested_role}</span>
          <span class="pri">P{sug.priority}</span>
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
      <li class="empty">No open suggestions — advisor monitoring UCI feed</li>
    {/each}
  </ul>
  {#each suggestions.filter((s) => s.status === "accepted") as sug (sug.suggestion_id)}
    <p class="accepted">✓ Accepted {sug.suggested_role} on {sug.target_entity_id}</p>
  {/each}
</section>

<style>
  .advisor-panel {
    border-bottom: 1px solid var(--glass-border);
    padding: 12px 14px;
    max-height: 280px;
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
    justify-content: space-between;
    margin-bottom: 4px;
  }
  .role {
    font-size: 10px;
    font-weight: 700;
    color: #a78bfa;
  }
  .pri {
    font-size: 10px;
    color: var(--text-muted);
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
