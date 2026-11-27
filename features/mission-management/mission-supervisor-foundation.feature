@mission-management @phase1
Feature: Mission management foundation
  Mission supervisors use durable organizational ownership, accountable tasks,
  and fleet overview without overloading tactical COP displays.

  Background:
    Given the mission-management seed is loaded
    And harness platform IDs are linked to organizational overlays

  @check:mm_support_multi
  Scenario: Operator supporting multiple aircraft
    Given operator OP-ALPHA is primary on COAL-F16C-01
    And OP-ALPHA supports COAL-F15E-01
    When ownership is queried
    Then primary and support responsibilities are listed separately
    And COAL-F15E-01 primary operator remains OP-STRIKE

  @check:mm_retain_primary
  Scenario: Operator retaining primary aircraft responsibility
    Given operator OP-ALPHA is primary on COAL-F16C-01
    When OP-ALPHA is added as support on another platform
    Then OP-ALPHA remains primary on COAL-F16C-01

  @check:mm_single_owner
  Scenario: Task having one accountable owner
    Given task TSK-M-SEAD-01 is active
    When the task is loaded
    Then accountable_owner_id is exactly OP-ALPHA
    And supporting operators are tracked separately

  @check:mm_reassign_ack
  Scenario: Task reassignment awaiting acknowledgement
    Given task TSK-M-SEAD-01 is owned by OP-ALPHA
    When a supervisor reassigns the task to OP-BRAVO without override
    Then acknowledgement_status is pending
    And OP-ALPHA remains accountable until OP-BRAVO acknowledges
    And prior assignment history is retained

  @check:mm_committed
  Scenario: Platform operational but fully committed
    Given platform COAL-F16C-01 is Operational with an active commitment
    When fleet overview is built
    Then operational availability is unavailable_for_additional
    And the platform is counted as committed

  @check:mm_reserve
  Scenario: Platform operational and held in reserve
    Given platform COAL-KC135-01 is Operational and held_in_reserve
    When fleet overview is built
    Then operational availability is available_reserved
    And the platform is not classified as inefficiently utilized

  @check:mm_workload_conflict
  Scenario: Operator workload conflict
    Given OP-ALPHA has primary and support aircraft plus active tasks
    When supervisor views operator workload
    Then contributing factors are listed
    And a conflict indicator is present
    And no 0-100 workload score is exposed

  @check:mm_stale
  Scenario: Stale telemetry
    Given a platform with stale or missing last_update_time
    When fleet overview is built
    Then the platform is flagged stale
    And technical readiness is not fabricated beyond Unknown

  @check:mm_unknown_ready
  Scenario: Unknown platform readiness
    Given a platform with no readiness value
    When fleet overview is built
    Then technical readiness is Unknown

  @check:mm_unauth
  Scenario: Unauthorized assignment changes
    Given actor role analyst
    When a reassignment is attempted
    Then the operation is forbidden
    And assignment state is unchanged

  @check:mm_evidence
  Scenario: Task completion requiring evidence
    Given task TSK-M-SEAD-01 requires evidence
    When completion is attempted without evidence
    Then the transition is rejected
    And completion with evidence succeeds and is audited

  @check:mm_fleet_progress
  Scenario: Supervisor viewing fleet-wide progress
    Given mission MSN-GULF-01 with milestones and tasks
    When supervisor requests fleet overview and mission progress
    Then aggregate platform counts are returned
    And mission progress is criteria-based
