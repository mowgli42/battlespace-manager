@mission-management @phase2
Feature: Mission resource management (Phase 2)
  Supervisors and team leads use team consoles, workload comparisons,
  commitments, mission progress, and conflict indicators without auto-assignment.

  Background:
    Given the mission-management seed v1.1 is loaded

  @check:mm2_team_console
  Scenario: Operating team console separates primary and support
    Given team TEAM-SEAD has primary platforms
    When the team console is requested
    Then primary aircraft are listed separately from supported aircraft
    And primary operators retain visibility of primary responsibilities
    And team workload exposes factor aggregates without a 0-100 score

  @check:mm2_team_compare
  Scenario: Team workload comparison
    When teams overview is requested
    Then each team reports active task and pending action factors
    And relative_load is higher, lower, or typical versus median
    And no team workload_score is exposed

  @check:mm2_operator_overview
  Scenario: Operator workload overview
    When operators workload overview is requested
    Then contributing factors are listed per operator
    And conflict indicators mark overloaded primary-plus-support operators
    And workload_score remains null

  @check:mm2_commitments
  Scenario: Platform commitments and operational availability
    Given COAL-F16C-01 is operational with an active commitment
    And COAL-KC135-01 is operational and held in reserve
    And COAL-F15E-01 has a scheduled commitment with estimated availability
    When platform commitments are queried
    Then committed platforms cannot accept additional work
    And reserve platforms remain available_reserved
    And estimated_available_at is reported for scheduled work

  @check:mm2_conflicts
  Scenario: Resource conflict indicators without auto-assignment
    When resource conflicts are requested
    Then blocked tasks and operator workload conflicts are included
    And every conflict has auto_action null
    And recommendations do not perform assignment

  @check:mm2_mission_progress
  Scenario: Mission progress with dependencies and constraints
    Given mission MSN-GULF-01 has a blocked CAS task waiting on SEAD
    When mission progress is requested
    Then task counts include blocked and deferred
    And dependencies or blocker reasons are listed
    And progress remains criteria-based
