<script>
  import { onMount } from "svelte";

  let {
    teamId = $bindable("TEAM-SEAD"),
    selectedPlatformId = $bindable(null),
    onSelectPlatform = () => {},
  } = $props();

  let teams = $state([]);
  let consoleData = $state(null);
  let error = $state("");
  let loading = $state(true);
  let section = $state("overview");

  const actorHeaders = {
    "X-Actor-Id": "OP-SUPER-2",
    "X-Actor-Role": "team_supervisor",
  };

  async function loadTeams() {
    const r = await fetch("/api/mission/teams", { headers: actorHeaders });
    if (r.ok) {
      const body = await r.json();
      teams = body.teams || [];
      if (!teamId && teams.length) teamId = teams[0].team_id;
    }
  }

  async function loadConsole() {
    if (!teamId) return;
    loading = true;
    error = "";
    try {
      const r = await fetch(`/api/mission/teams/${encodeURIComponent(teamId)}/console`, {
        headers: actorHeaders,
      });
      if (!r.ok) throw new Error(`team console ${r.status}`);
      consoleData = await r.json();
    } catch (e) {
      error = String(e.message || e);
      consoleData = null;
    } finally {
      loading = false;
    }
  }

  async function refresh() {
    await loadTeams();
    await loadConsole();
  }

  onMount(() => {
    void refresh();
    const t = setInterval(() => void loadConsole(), 15000);
    return () => clearInterval(t);
  });

  $effect(() => {
    teamId;
    void loadConsole();
  });

  let wl = $derived(consoleData?.workload || {});
</script>

<div class="team-console">
  <div class="header">
    <div>
      <h2>Operating Team Console</h2>
      <p class="hint">
        Primary vs support responsibilities · team workload factors (not a capacity score) ·
        {consoleData?.generated_at || "—"}
      </p>
    </div>
    <div class="controls">
      <label>
        Team
        <select bind:value={teamId}>
          {#each teams as t (t.team_id)}
            <option value={t.team_id}>{t.name}</option>
          {/each}
        </select>
      </label>
      <button type="button" onclick={() => refresh()}>Refresh</button>
    </div>
  </div>

  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}
  {#if loading && !consoleData}
    <p class="hint">Loading team console…</p>
  {/if}

  {#if consoleData}
    <p class="note">{consoleData.note}</p>

    <div class="counts" role="group" aria-label="Team workload factors">
      <div class="count"><span class="n">{wl.primary_platforms ?? 0}</span><span class="l">Primary acft</span></div>
      <div class="count"><span class="n">{wl.supported_platforms ?? 0}</span><span class="l">Supported</span></div>
      <div class="count"><span class="n">{wl.active_tasks ?? 0}</span><span class="l">Active tasks</span></div>
      <div class="count warn"><span class="n">{wl.pending_acknowledgements ?? 0}</span><span class="l">Pending ack</span></div>
      <div class="count danger"><span class="n">{wl.blocked_tasks ?? 0}</span><span class="l">Blocked</span></div>
      <div class="count warn"><span class="n">{wl.operators_with_conflict ?? 0}</span><span class="l">Op conflicts</span></div>
      <div class="count warn"><span class="n">{wl.stale_platforms ?? 0}</span><span class="l">Stale</span></div>
      <div class="count"><span class="n">{wl.unresolved_exceptions ?? 0}</span><span class="l">Exceptions</span></div>
    </div>

    <div class="section-tabs">
      <button type="button" class:active={section === "overview"} onclick={() => (section = "overview")}>Aircraft</button>
      <button type="button" class:active={section === "ops"} onclick={() => (section = "ops")}>Operators</button>
      <button type="button" class:active={section === "tasks"} onclick={() => (section = "tasks")}>Tasks</button>
      <button type="button" class:active={section === "missions"} onclick={() => (section = "missions")}>Missions</button>
    </div>

    {#if section === "overview"}
      <div class="cols">
        <section>
          <h3>Primary aircraft</h3>
          <ul>
            {#each consoleData.primary_aircraft || [] as p (p.platform_id)}
              <li>
                <button
                  type="button"
                  class="linkish"
                  onclick={() => {
                    selectedPlatformId = p.platform_id;
                    onSelectPlatform(p.platform_id);
                  }}
                >
                  <code>{p.platform_id}</code>
                  {#if p.callsign}<span class="muted"> · {p.callsign}</span>{/if}
                </button>
                <span class="ready">{p.technical_readiness}</span>
                {#if p.stale}<span class="badge warn">stale</span>{/if}
                {#if p.held_in_reserve}<span class="badge">reserve</span>{/if}
                <span class="muted">owner {p.primary_operator_id || "—"}</span>
              </li>
            {:else}
              <li class="muted">None</li>
            {/each}
          </ul>
        </section>
        <section>
          <h3>Supported aircraft</h3>
          <ul>
            {#each consoleData.supported_aircraft || [] as p (p.platform_id)}
              <li>
                <code>{p.platform_id}</code>
                <span class="ready">{p.technical_readiness}</span>
                {#if p.stale}<span class="badge warn">stale</span>{/if}
                <span class="muted">primary remains {p.primary_operator_id || "—"}</span>
              </li>
            {:else}
              <li class="muted">None</li>
            {/each}
          </ul>
        </section>
      </div>
    {/if}

    {#if section === "ops"}
      <div class="cols">
        <section>
          <h3>Primary operators</h3>
          <p class="hint">{(consoleData.primary_operators || []).join(", ") || "—"}</p>
          <h3>Supporting operators</h3>
          <p class="hint">{(consoleData.supporting_operators || []).join(", ") || "—"}</p>
        </section>
        <section>
          <h3>Member workload factors</h3>
          <ul>
            {#each consoleData.members || [] as m (m.operator.operator_id)}
              <li>
                <strong>{m.operator.name}</strong>
                <span class="muted"> · {m.operator.availability_state}</span>
                {#if m.factors.conflict_indicator}<span class="badge warn">conflict</span>{/if}
                <div class="muted">
                  primary {(m.factors.primary_aircraft || []).join(", ") || "—"} · support
                  {(m.factors.supported_aircraft || []).join(", ") || "—"} · tasks
                  {m.factors.active_tasks ?? 0} · pending ack {m.factors.pending_acknowledgements ?? 0}
                </div>
              </li>
            {/each}
          </ul>
        </section>
      </div>
    {/if}

    {#if section === "tasks"}
      <section>
        <h3>Active tasks</h3>
        <ul>
          {#each consoleData.active_tasks || [] as t (t.task_id)}
            <li>
              <code>{t.task_id}</code> · {t.status} · owner {t.accountable_owner_id}
              <span class="muted"> · {t.description}</span>
            </li>
          {:else}
            <li class="muted">None</li>
          {/each}
        </ul>
        <h3>Pending acknowledgements</h3>
        <ul>
          {#each consoleData.pending_acknowledgements || [] as t (t.task_id)}
            <li>
              <code>{t.task_id}</code> → pending {t.pending_owner_id}
              <span class="muted">(current owner {t.accountable_owner_id})</span>
            </li>
          {:else}
            <li class="muted">None</li>
          {/each}
        </ul>
        <h3>Blocked</h3>
        <ul>
          {#each consoleData.blocked_tasks || [] as t (t.task_id)}
            <li>
              <code>{t.task_id}</code>
              <span class="badge danger">blocked</span>
              <span class="muted">{t.blocker_reason}</span>
            </li>
          {:else}
            <li class="muted">None</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if section === "missions"}
      <section>
        <h3>Current missions</h3>
        <ul>
          {#each consoleData.current_missions || [] as m (m.mission_id)}
            <li>
              <strong>{m.name}</strong>
              <span class="muted"> · {m.mission_id} · {m.status}</span>
              <div class="muted">{m.description}</div>
            </li>
          {:else}
            <li class="muted">None</li>
          {/each}
        </ul>
        <h3>Open exceptions</h3>
        <ul>
          {#each consoleData.alerts || [] as a (a.alert_id)}
            <li>
              <span class="badge sev-{a.severity}">{a.severity}</span>
              {a.description}
            </li>
          {:else}
            <li class="muted">None</li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</div>

<style>
  .team-console {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: 12px 16px;
    gap: 12px;
    overflow: auto;
  }
  .header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  h2 {
    margin: 0;
    font-size: 13px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ok);
  }
  h3 {
    margin: 8px 0 6px;
    font-size: 12px;
    color: var(--accent);
  }
  .hint,
  .note,
  .muted {
    color: var(--text-muted);
    font-size: 11px;
  }
  .note {
    margin: 0;
  }
  .error {
    color: var(--danger);
    font-size: 12px;
  }
  .controls {
    display: flex;
    gap: 8px;
    align-items: end;
  }
  label {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--text-muted);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  select,
  button {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-primary);
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
  }
  button {
    cursor: pointer;
  }
  .counts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .count {
    min-width: 84px;
    padding: 8px 10px;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.25);
  }
  .count .n {
    display: block;
    font-size: 18px;
    font-variant-numeric: tabular-nums;
  }
  .count .l {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  .count.warn .n {
    color: var(--warn);
  }
  .count.danger .n {
    color: var(--danger);
  }
  .section-tabs {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .section-tabs button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px;
  }
  ul {
    margin: 0;
    padding-left: 16px;
    font-size: 12px;
  }
  li {
    margin-bottom: 6px;
  }
  code {
    color: var(--ok);
  }
  .badge {
    display: inline-block;
    margin-left: 4px;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 10px;
    border: 1px solid var(--glass-border);
  }
  .badge.warn {
    color: var(--warn);
  }
  .badge.danger {
    color: var(--danger);
  }
  .sev-Critical {
    border-color: var(--danger);
    color: var(--danger);
  }
  .sev-Attention {
    border-color: var(--warn);
    color: var(--warn);
  }
  .sev-Informational {
    border-color: var(--accent);
    color: var(--accent);
  }
  .ready {
    margin-left: 6px;
    font-size: 11px;
  }
  .linkish {
    background: none;
    border: none;
    padding: 0;
    color: inherit;
    cursor: pointer;
    font: inherit;
  }
</style>
