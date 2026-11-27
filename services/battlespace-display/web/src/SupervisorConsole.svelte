<script>
  import { onMount } from "svelte";

  let {
    selectedPlatformId = $bindable(null),
    onSelectPlatform = () => {},
  } = $props();

  let fleet = $state({ counts: {}, platforms: [], generated_at: "" });
  let detail = $state(null);
  let progress = $state(null);
  let alerts = $state([]);
  let workload = $state(null);
  let teamsOverview = $state({ teams: [] });
  let operatorsWorkload = $state({ operators: [], conflict_count: 0 });
  let conflicts = $state({ conflicts: [], counts: {}, total: 0 });
  let commitments = $state(null);
  let section = $state("fleet");
  let error = $state("");
  let loading = $state(true);

  const actorHeaders = {
    "X-Actor-Id": "OP-SUPER-1",
    "X-Actor-Role": "mission_supervisor",
  };

  async function loadFleet() {
    loading = true;
    error = "";
    try {
      const r = await fetch("/api/mission/fleet", { headers: actorHeaders });
      if (!r.ok) throw new Error(`fleet ${r.status}`);
      fleet = await r.json();
      const ar = await fetch("/api/mission/alerts", { headers: actorHeaders });
      if (ar.ok) {
        const body = await ar.json();
        alerts = body.alerts || [];
      }
      const pr = await fetch("/api/mission/missions/MSN-GULF-01/progress", { headers: actorHeaders });
      if (pr.ok) progress = await pr.json();
      const tr = await fetch("/api/mission/teams/overview", { headers: actorHeaders });
      if (tr.ok) teamsOverview = await tr.json();
      const ow = await fetch("/api/mission/operators/workload", { headers: actorHeaders });
      if (ow.ok) operatorsWorkload = await ow.json();
      const cr = await fetch("/api/mission/conflicts", { headers: actorHeaders });
      if (cr.ok) conflicts = await cr.json();
    } catch (e) {
      error = String(e.message || e);
    } finally {
      loading = false;
    }
  }

  async function openPlatform(platformId) {
    selectedPlatformId = platformId;
    onSelectPlatform(platformId);
    section = "platform";
    try {
      const r = await fetch(`/api/mission/platforms/${encodeURIComponent(platformId)}`, {
        headers: actorHeaders,
      });
      if (!r.ok) throw new Error(`platform ${r.status}`);
      detail = await r.json();
      const opId = detail?.organization?.primary_operator_id;
      if (opId) {
        const wr = await fetch(`/api/mission/operators/${encodeURIComponent(opId)}/workload`, {
          headers: actorHeaders,
        });
        workload = wr.ok ? await wr.json() : null;
      } else {
        workload = null;
      }
      const cr = await fetch(`/api/mission/platforms/${encodeURIComponent(platformId)}/commitments`, {
        headers: actorHeaders,
      });
      commitments = cr.ok ? await cr.json() : null;
    } catch (e) {
      error = String(e.message || e);
    }
  }

  async function ackAlert(alertId) {
    const r = await fetch(`/api/mission/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
      method: "POST",
      headers: { ...actorHeaders, "Content-Type": "application/json" },
      body: "{}",
    });
    if (r.ok) await loadFleet();
  }

  onMount(() => {
    void loadFleet();
    const t = setInterval(() => void loadFleet(), 15000);
    return () => clearInterval(t);
  });

  let counts = $derived(fleet.counts || {});
</script>

<div class="supervisor">
  <div class="header">
    <div>
      <h2>Mission Supervisor Console</h2>
      <p class="hint">
        Fleet ownership, readiness, and mission progress · separate from tactical COP tabs ·
        {fleet.generated_at || "—"}
      </p>
    </div>
    <div class="section-tabs" role="tablist">
      <button type="button" class:active={section === "fleet"} onclick={() => (section = "fleet")}>Fleet</button>
      <button type="button" class:active={section === "teams"} onclick={() => (section = "teams")}>Teams</button>
      <button type="button" class:active={section === "workload"} onclick={() => (section = "workload")}>Workload</button>
      <button type="button" class:active={section === "conflicts"} onclick={() => (section = "conflicts")}>Conflicts</button>
      <button type="button" class:active={section === "mission"} onclick={() => (section = "mission")}>Mission</button>
      <button type="button" class:active={section === "alerts"} onclick={() => (section = "alerts")}>Exceptions</button>
      <button type="button" class:active={section === "platform"} disabled={!detail} onclick={() => (section = "platform")}>
        Platform
      </button>
      <button type="button" class="refresh" onclick={() => loadFleet()}>Refresh</button>
    </div>
  </div>

  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}
  {#if loading && !fleet.platforms?.length}
    <p class="hint">Loading fleet overview…</p>
  {/if}

  {#if section === "fleet"}
    <div class="counts" role="group" aria-label="Fleet summary">
      <div class="count"><span class="n">{counts.total ?? 0}</span><span class="l">Total</span></div>
      <div class="count ok"><span class="n">{counts.operational ?? 0}</span><span class="l">Operational</span></div>
      <div class="count warn"><span class="n">{counts.degraded ?? 0}</span><span class="l">Degraded</span></div>
      <div class="count danger"><span class="n">{counts.unavailable ?? 0}</span><span class="l">Unavailable</span></div>
      <div class="count"><span class="n">{counts.unknown ?? 0}</span><span class="l">Unknown</span></div>
      <div class="count"><span class="n">{counts.committed ?? 0}</span><span class="l">Committed</span></div>
      <div class="count ok"><span class="n">{counts.uncommitted_operational ?? 0}</span><span class="l">Uncommitted ops</span></div>
      <div class="count warn"><span class="n">{counts.stale_telemetry ?? 0}</span><span class="l">Stale</span></div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Platform</th>
            <th>Tech readiness</th>
            <th>Op availability</th>
            <th>Commitment</th>
            <th>Primary team</th>
            <th>Primary operator</th>
            <th>Tasks</th>
            <th>Last update</th>
            <th>Exceptions</th>
          </tr>
        </thead>
        <tbody>
          {#each fleet.platforms || [] as row (row.platform_id)}
            <tr
              class:selected={selectedPlatformId === row.platform_id}
              class:stale={row.stale}
              onclick={() => openPlatform(row.platform_id)}
            >
              <td>
                <code>{row.platform_id}</code>
                {#if row.callsign}<span class="muted"> · {row.callsign}</span>{/if}
                {#if row.held_in_reserve}<span class="badge reserve">Reserve</span>{/if}
              </td>
              <td class="ready-{row.technical_readiness}">{row.technical_readiness}</td>
              <td>
                {row.operational_availability?.state || "—"}
                <span class="muted block">{row.operational_availability?.reason || ""}</span>
              </td>
              <td>{row.current_commitment || "—"}</td>
              <td>{row.primary_team_name || row.primary_team_id || "—"}</td>
              <td>{row.primary_operator_name || row.primary_operator_id || "—"}</td>
              <td>{row.active_task_count ?? 0}</td>
              <td class:stale-text={row.stale}>{row.last_update_time || (row.stale ? "stale/missing" : "—")}</td>
              <td>
                {#each row.exceptions || [] as ex}
                  <span class="badge sev-{ex.severity}">{ex.code}</span>
                {/each}
                {#if !(row.exceptions || []).length}<span class="muted">—</span>{/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if section === "teams"}
    <p class="hint">{teamsOverview.note || "Team factor comparison (not a capacity score)."}</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Team</th>
            <th>Supervisor</th>
            <th>Primary acft</th>
            <th>Supported</th>
            <th>Active tasks</th>
            <th>Pending actions</th>
            <th>Exceptions</th>
            <th>Relative load</th>
            <th>Imbalance</th>
          </tr>
        </thead>
        <tbody>
          {#each teamsOverview.teams || [] as t (t.team_id)}
            <tr>
              <td>{t.name} <span class="muted">({t.team_id})</span></td>
              <td>{t.supervisor_id || "—"}</td>
              <td>{t.primary_aircraft_count ?? 0}</td>
              <td>{t.supported_aircraft_count ?? 0}</td>
              <td>{t.active_task_count ?? 0}</td>
              <td>{t.pending_actions ?? 0}</td>
              <td>{t.unresolved_exceptions ?? 0}</td>
              <td>{t.relative_load || "—"}</td>
              <td>{t.imbalance_indicator ? "yes" : "no"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if section === "workload"}
    <p class="hint">{operatorsWorkload.note}</p>
    <p class="hint">Operators with conflict indicator: {operatorsWorkload.conflict_count ?? 0}</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Operator</th>
            <th>Availability</th>
            <th>Primary aircraft</th>
            <th>Supported</th>
            <th>Active tasks</th>
            <th>Pending ack</th>
            <th>Time-sensitive</th>
            <th>Exceptions</th>
            <th>Conflict</th>
          </tr>
        </thead>
        <tbody>
          {#each operatorsWorkload.operators || [] as row (row.operator.operator_id)}
            <tr class:stale={row.conflict_indicator}>
              <td>{row.operator.name} <span class="muted">({row.operator.operator_id})</span></td>
              <td>{row.factors?.availability_state || "—"}</td>
              <td>{(row.factors?.primary_aircraft || []).join(", ") || "—"}</td>
              <td>{(row.factors?.supported_aircraft || []).join(", ") || "—"}</td>
              <td>{row.factors?.active_tasks ?? 0}</td>
              <td>{row.factors?.pending_acknowledgements ?? 0}</td>
              <td>{row.factors?.time_sensitive_tasks ?? 0}</td>
              <td>{row.factors?.unresolved_exceptions ?? 0}</td>
              <td>{row.conflict_indicator ? "yes" : "no"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if section === "conflicts"}
    <p class="hint">{conflicts.note}</p>
    <div class="counts">
      <div class="count danger"><span class="n">{conflicts.counts?.Critical ?? 0}</span><span class="l">Critical</span></div>
      <div class="count warn"><span class="n">{conflicts.counts?.Attention ?? 0}</span><span class="l">Attention</span></div>
      <div class="count"><span class="n">{conflicts.counts?.Informational ?? 0}</span><span class="l">Informational</span></div>
      <div class="count"><span class="n">{conflicts.total ?? 0}</span><span class="l">Total</span></div>
    </div>
    <div class="alerts">
      {#each conflicts.conflicts || [] as c (c.conflict_id)}
        <article class="alert sev-{c.severity}">
          <header>
            <span class="badge sev-{c.severity}">{c.severity}</span>
            <span class="badge">{c.kind}</span>
            <code>{c.entity_type}:{c.entity_id}</code>
          </header>
          <p>{c.description}</p>
          <p class="hint">Recommendation: {c.recommendation}</p>
          <p class="hint">Auto-action: {c.auto_action ?? "none (human decision required)"}</p>
        </article>
      {:else}
        <p class="hint">No resource conflicts.</p>
      {/each}
    </div>
  {/if}

  {#if section === "mission" && progress}
    <div class="mission-panel">
      <h3>{progress.mission?.name || progress.mission?.mission_id}</h3>
      <p class="hint">{progress.note}</p>
      <div class="objectives">
        <h4>Objectives</h4>
        <ul>
          {#each progress.objectives || [] as obj}
            <li>{obj}</li>
          {/each}
        </ul>
      </div>
      <div class="milestones">
        <h4>
          Milestones · {progress.milestone_completion?.completed ?? 0}/{progress.milestone_completion?.total ?? 0}
        </h4>
        <ul>
          {#each progress.required_milestones || [] as ms}
            <li><span class="badge">{ms.status}</span> {ms.name}</li>
          {/each}
        </ul>
      </div>
      <div class="counts">
        <div class="count ok"><span class="n">{progress.task_counts?.completed ?? 0}</span><span class="l">Completed</span></div>
        <div class="count"><span class="n">{progress.task_counts?.in_progress ?? 0}</span><span class="l">In progress</span></div>
        <div class="count danger"><span class="n">{progress.task_counts?.blocked ?? 0}</span><span class="l">Blocked</span></div>
        <div class="count warn"><span class="n">{progress.task_counts?.deferred ?? 0}</span><span class="l">Deferred</span></div>
        <div class="count danger"><span class="n">{progress.task_counts?.overdue ?? 0}</span><span class="l">Overdue</span></div>
        <div class="count"><span class="n">{progress.task_counts?.upcoming ?? 0}</span><span class="l">Upcoming due</span></div>
      </div>
      <h4>Dependencies / blockers</h4>
      <ul>
        {#each progress.dependencies || [] as d}
          <li>
            <code>{d.task_id}</code>
            {#if d.depends_on}<span class="muted"> depends on {d.depends_on}</span>{/if}
            <span class="muted"> — {d.reason}</span>
          </li>
        {:else}
          <li class="muted">None documented</li>
        {/each}
      </ul>
      <h4>Resource constraints</h4>
      <ul>
        {#each progress.resource_constraints || [] as rc}
          <li><code>{rc.task_id}</code> · {rc.platform_id} · {rc.constraint}</li>
        {:else}
          <li class="muted">None</li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if section === "alerts"}
    <div class="alerts">
      {#each alerts as alert (alert.alert_id)}
        <article class="alert sev-{alert.severity}">
          <header>
            <span class="badge sev-{alert.severity}">{alert.severity}</span>
            <code>{alert.entity_type}:{alert.entity_id}</code>
            <span class="muted">{alert.created_at}</span>
          </header>
          <p>{alert.description}</p>
          <p class="hint">Action: {alert.required_action || "—"}</p>
          <p class="hint">
            Ack: {alert.acknowledgement_status} · Resolution: {alert.resolution_status}
          </p>
          {#if alert.acknowledgement_status !== "acknowledged"}
            <button type="button" onclick={() => ackAlert(alert.alert_id)}>Acknowledge</button>
          {/if}
        </article>
      {:else}
        <p class="hint">No exceptions.</p>
      {/each}
    </div>
  {/if}

  {#if section === "platform" && detail}
    <div class="platform-detail">
      <h3>
        {detail.organization?.platform_id}
        <span class="muted">{detail.organization?.platform_type}</span>
      </h3>
      <div class="detail-grid">
        <div><span class="lbl">Primary team</span> {detail.organization?.primary_team_id || "—"}</div>
        <div><span class="lbl">Primary operator</span> {detail.organization?.primary_operator_id || "—"}</div>
        <div>
          <span class="lbl">Supporting operators</span>
          {(detail.organization?.support_operator_ids || []).join(", ") || "—"}
        </div>
        <div><span class="lbl">Tech readiness</span> {detail.fleet_row?.technical_readiness || "—"}</div>
        <div>
          <span class="lbl">Op availability</span>
          {detail.fleet_row?.operational_availability?.state || "—"}
        </div>
        <div><span class="lbl">Reserve</span> {detail.organization?.held_in_reserve ? "yes" : "no"}</div>
        <div><span class="lbl">Telemetry</span> {detail.fleet_row?.stale ? "stale/unknown" : "fresh"}</div>
      </div>

      <h4>Tasks</h4>
      <ul>
        {#each detail.tasks || [] as t}
          <li>
            <code>{t.task_id}</code> · {t.status} · owner {t.accountable_owner_id}
            {#if t.pending_owner_id}<span class="badge warn">pending ack → {t.pending_owner_id}</span>{/if}
          </li>
        {:else}
          <li class="muted">No mission tasks linked</li>
        {/each}
      </ul>

      <h4>Assignment history</h4>
      <ul>
        {#each detail.assignment_history || [] as a}
          <li>
            <code>{a.assignment_id}</code> · {a.responsibility_type} · {a.assignment_status} ·
            {a.operator_id} · ack {a.acknowledgement_status}
          </li>
        {:else}
          <li class="muted">No assignment history</li>
        {/each}
      </ul>

      {#if commitments}
        <h4>Commitments & operational availability</h4>
        <p class="hint">{commitments.note}</p>
        <div class="detail-grid">
          <div>
            <span class="lbl">Op availability</span>
            {commitments.operational_availability?.state || "—"}
            <span class="muted block">{commitments.operational_availability?.reason || ""}</span>
          </div>
          <div>
            <span class="lbl">Can accept additional</span>
            {commitments.operational_availability?.can_accept_additional ? "yes" : "no"}
          </div>
          <div>
            <span class="lbl">Est. available</span>
            {commitments.operational_availability?.estimated_available_at || "—"}
          </div>
        </div>
        <ul>
          {#each [...(commitments.active_commitments || []), ...(commitments.scheduled_commitments || [])] as c}
            <li>
              <code>{c.commitment_id}</code> · {c.status} · {c.kind} · {c.label || "—"}
              {#if c.estimated_available_at}
                <span class="muted"> · avail {c.estimated_available_at}</span>
              {/if}
            </li>
          {:else}
            <li class="muted">No scheduled/active commitments</li>
          {/each}
        </ul>
      {/if}

      {#if workload}
        <h4>Primary operator workload factors (estimated contributors — not a capacity score)</h4>
        <ul class="factors">
          <li>Primary aircraft: {(workload.factors?.primary_aircraft || []).join(", ") || "—"}</li>
          <li>Supported aircraft: {(workload.factors?.supported_aircraft || []).join(", ") || "—"}</li>
          <li>Active tasks: {workload.factors?.active_tasks ?? 0}</li>
          <li>Pending acknowledgements: {workload.factors?.pending_acknowledgements ?? 0}</li>
          <li>Time-sensitive tasks: {workload.factors?.time_sensitive_tasks ?? 0}</li>
          <li>Unresolved exceptions: {workload.factors?.unresolved_exceptions ?? 0}</li>
          <li>Availability: {workload.factors?.availability_state || "—"}</li>
          <li>
            Conflict indicator: {workload.conflict_indicator ? "yes" : "no"}
          </li>
        </ul>
      {/if}
    </div>
  {/if}
</div>

<style>
  .supervisor {
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
    align-items: flex-start;
  }
  h2 {
    margin: 0;
    font-size: 13px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ok);
  }
  h3,
  h4 {
    margin: 8px 0 6px;
    font-size: 12px;
    color: var(--accent);
  }
  .hint {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--text-muted);
  }
  .error {
    color: var(--danger);
    font-size: 12px;
  }
  .section-tabs {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .section-tabs button {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-primary);
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
  }
  .section-tabs button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
  .section-tabs button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .counts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .count {
    min-width: 88px;
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
  .count.ok .n {
    color: var(--ok);
  }
  .count.warn .n {
    color: var(--warn);
  }
  .count.danger .n {
    color: var(--danger);
  }
  .table-wrap {
    overflow: auto;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }
  th,
  td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    text-align: left;
    vertical-align: top;
  }
  th {
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 10px;
    position: sticky;
    top: 0;
    background: #0a1524;
  }
  tbody tr {
    cursor: pointer;
  }
  tbody tr:hover,
  tbody tr.selected {
    background: rgba(0, 212, 255, 0.06);
  }
  tbody tr.stale {
    background: rgba(251, 191, 36, 0.05);
  }
  .ready-Operational {
    color: var(--ok);
  }
  .ready-Degraded {
    color: var(--warn);
  }
  .ready-Unavailable {
    color: var(--danger);
  }
  .ready-Unknown {
    color: var(--text-muted);
  }
  .muted {
    color: var(--text-muted);
  }
  .muted.block {
    display: block;
    font-size: 10px;
  }
  .stale-text {
    color: var(--warn);
  }
  .badge {
    display: inline-block;
    margin: 1px 2px;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 10px;
    border: 1px solid var(--glass-border);
  }
  .badge.reserve {
    color: var(--accent);
  }
  .badge.warn {
    color: var(--warn);
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
  .alerts {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .alert {
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    padding: 10px 12px;
  }
  .alert header {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 4px;
  }
  .detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 8px;
    margin-bottom: 8px;
  }
  .lbl {
    display: block;
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  code {
    color: var(--ok);
  }
  .factors {
    font-size: 12px;
  }
</style>
