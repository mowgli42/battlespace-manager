@harness @battlespace-display
Feature: Battlespace F2T2EA and tasking happy path
  CAOC operators use battlespace-display harness mode for picture streaming,
  attention rail, kill-chain, tasking queue, and route-threat workflows.

  Background:
    Given the battlespace-display harness scenario is loaded
    And BATTLESPACE_HARNESS mode is enabled

  @check:picture_contract @check:timeline_view @check:mission_thread
  Scenario: Operator receives a contract-valid live picture
    When the harness picture is built for SSE and GET /api/picture
    Then the picture passes contract validation
    And timeline_view is populated
    And mission_thread exposes F2T2EA phases and phase_counts

  @check:attention_tst @check:attention_popup @check:route_threats
  Scenario: Attention rail surfaces TST, POPUP, and route threats
    When the operator reviews the attention rail and Routes tab
    Then TST items appear in the attention queue
    And POPUP items appear in the attention queue
    And route_threats list impacted routes

  @check:fkcm_targets @check:mission_thread
  Scenario: Kill chain shows FKCM targets across F2T2EA phases
    When the operator opens the Kill chain tab
    Then FKCM targets include Find and Target phases
    And the F2T2EA phase rail reflects mission_thread counts

  @check:tst_tasks @check:unassigned_tasks @check:high_priority_unassigned
  Scenario: Decisions queue offers TST and high-priority tasking
    When the operator opens the Decisions / tasking queue
    Then TST tasks are present in task_rows
    And unassigned tasks are available to assign
    And at least one high-priority unassigned task is queued
