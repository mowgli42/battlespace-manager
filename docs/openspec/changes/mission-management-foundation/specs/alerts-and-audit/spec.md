## ADDED Requirements

### Requirement: Exception severity levels
The system SHALL provide Critical, Attention, and Informational alerts with acknowledgement status distinct from resolution status.

#### Scenario: Acknowledge without resolve
- GIVEN a Critical alert on a platform
- WHEN a supervisor acknowledges the alert
- THEN acknowledgement_status becomes acknowledged
- AND resolution_status remains open until explicitly resolved

### Requirement: Auditable ownership changes
The system SHALL persist an audit event for every material ownership or assignment change including actor, timestamps, previous and new values, reason, and source.

#### Scenario: Ownership change audited
- GIVEN a successful reassignment acknowledgement
- WHEN audit history is queried for the task
- THEN an event records previous and new accountable owners with event_timestamp and received_timestamp
