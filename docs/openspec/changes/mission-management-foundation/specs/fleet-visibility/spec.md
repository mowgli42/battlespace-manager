## ADDED Requirements

### Requirement: Supervisor fleet overview
The system SHALL provide a fleet overview that reports total, operational, degraded, unavailable, unknown, committed, uncommitted-operational, upcoming-availability, and stale-telemetry platform counts.

#### Scenario: Supervisor views fleet-wide progress
- GIVEN seeded platforms linked to picture telemetry
- WHEN a mission supervisor requests GET /api/mission/fleet
- THEN the response includes aggregate counts and per-platform rows with identifier, technical readiness, operational availability, primary team, primary operator, active task count, last update time, and exceptions
- AND technical readiness is distinct from operational availability

### Requirement: Stale and unknown telemetry
The system SHALL mark platforms with missing readiness as Unknown and platforms whose last_update_time exceeds the configured stale threshold as stale without inventing readiness values.

#### Scenario: Stale telemetry
- GIVEN a platform whose last_update_time is older than the stale threshold
- WHEN the fleet overview is built
- THEN the platform is flagged stale
- AND its technical readiness is not fabricated

#### Scenario: Unknown platform readiness
- GIVEN a platform with no readiness value from the picture source
- WHEN the fleet overview is built
- THEN technical readiness is Unknown
