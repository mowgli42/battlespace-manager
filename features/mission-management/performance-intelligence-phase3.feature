@mission-management @phase3
Feature: Mission performance intelligence (Phase 3)
  Supervisors use historical utilization, milestone analytics, health
  integration, post-flight review, and bottleneck analysis without
  inventing readiness or auto-assigning work.

  Background:
    Given the mission-management seed v1.2 is loaded with utilization samples

  @check:mm3_utilization
  Scenario: Historical platform utilization with reserve exclusion
    When utilization analytics are requested for the seed window
    Then mission-assigned and operationally-available minutes are reported
    And reserved platform minutes are intentional_reserve_minutes
    And reserved platforms are excluded from the utilization denominator
    And stale or unknown samples are reported separately

  @check:mm3_uncommitted
  Scenario: Uncommitted operational time
    When utilization analytics are requested
    Then uncommitted operational minutes are reported for non-reserved platforms
    And reserved time is not classified as inefficient utilization

  @check:mm3_milestones
  Scenario: Mission milestone analytics
    Given mission MSN-GULF-01 has required milestones
    When milestone analytics are requested
    Then completed and total required milestones are returned with an explicit ratio

  @check:mm3_health
  Scenario: Aircraft and sensor health from picture only
    Given a picture with subsystem states for a platform
    When health analytics are requested
    Then readiness and degraded sensors come from picture fields
    And missing picture data is Unknown or empty rather than invented

  @check:mm3_postflight
  Scenario: Post-flight performance review
    When post-flight review is requested for MSN-GULF-01
    Then task outcomes, evidence, delays, and ownership history are summarized
    And mission completion is not inferred from telemetry alone

  @check:mm3_bottlenecks
  Scenario: Workload and resource bottleneck analysis
    When bottleneck analysis is requested
    Then ranked bottlenecks include recommendations
    And every bottleneck has auto_action null
