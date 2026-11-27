Feature: Mission bus, production SSO, and continuous sampler
  Deferred stack after Phase 3 — Redis fan-out, JWT identity, background samples.
  SQLite remains authoritative; bus publish is best-effort.

  @check:mm_bus_topics
  Scenario: Mission events publish on uci.mission.* topics
    Given durable audit is written to SQLite
    When a platform ownership mutation commits
    Then a uci.mission.* envelope is published with schema uci.mission.event/v1
    And topic names do not collide with o-my uci.mission.plan*

  @check:mm_sso_jwt
  Scenario: Production JWT SSO with harness header fallback
    Given MISSION_AUTH_MODE is jwt
    When a valid Bearer token is presented
    Then the actor is taken from JWT claims
    And when MISSION_AUTH_ALLOW_HEADER_FALLBACK is enabled without a Bearer token
    Then X-Actor-Id and X-Actor-Role remain accepted for harness

  @check:mm_sampler
  Scenario: Continuous utilization sampler
    Given MISSION_SAMPLER_ENABLED is set
    When the background sampler ticks
    Then utilization samples are recorded without inventing readiness
