@harness @rf-display
Feature: RF spectrum EMSO deconfliction happy path
  Spectrum operators use rf-display harness mode to inspect four-column
  occupancy, JRFL/EMCON constraints, and deconfliction conflicts.

  Background:
    Given the rf-display harness scenario is loaded
    And RF_HARNESS mode is enabled

  @check:four_spectrum_columns @check:threat_radar_assets @check:jammer_assets @check:comm_assets @check:support_assets @check:gps_support
  Scenario: Operator sees four-column spectrum occupancy
    When the harness RF picture is built
    Then spectrum_columns has threat_radars, jammers, comm, and support
    And each column has assets
    And support includes GPS L1

  @check:jrfl_entries @check:emcon_areas @check:deconfliction_summary @check:overlap_graph
  Scenario: Operator reviews JRFL, EMCON, and overlap conflicts
    When the operator inspects the deconfliction strip and spectrum connectors
    Then JRFL entries are present
    And EMCON areas are present
    And deconfliction_summary is populated
    And spectrum_columns exposes overlap_bands

  @check:spectrum_rows @check:itu_band_summary @check:geo_locations
  Scenario: Operator filters spectrum by band and geography
    When the operator uses the ITU band summary and geo map filter
    Then spectrum occupancy rows are available
    And the nine-band ITU spectrum summary is active
    And emitters include lat/lon for map filtering
