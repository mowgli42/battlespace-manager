@harness @entity-display
Feature: Entity display C2 map happy path
  Operators use entity-display in harness mode to inspect the fused C2 picture
  — tracks, fog, routes, and alerts — without a live Redis bus.

  Background:
    Given the entity-display harness scenario is loaded
    And ENTITY_HARNESS mode is enabled

  @check:detected_tracks @check:map_view
  Scenario: Operator sees fused tracks on the Gulf War map
    When the harness snapshot is built
    Then detected tracks are present on the picture
    And map_view centers on the Gulf War bbox

  @check:fog_zones @check:route_corridors @check:route_target_alerts @check:overlay_summary
  Scenario: Operator reviews fog, routes, and route-target alerts
    When the operator enables Fog, Routes, and Alerts layers
    Then fog_zones overlay is present
    And platform route corridors are sampled
    And route-target alerts are available
    And the overlay summary is populated

  @check:undetected_threats
  Scenario: Undetected threats stay off the track list
    When the harness snapshot is built
    Then undetected threats are counted in the overlay summary
    And undetected threat ids are not leaked as tracks
