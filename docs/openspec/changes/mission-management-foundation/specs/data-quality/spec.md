## ADDED Requirements

### Requirement: Source and received timestamps
The system SHALL store source event time and received time separately when available and use UTC ISO-8601 as the internal time standard.

#### Scenario: Audit timestamps
- GIVEN an assignment transition is committed
- WHEN the audit event is persisted
- THEN event_timestamp and received_timestamp are both present in UTC

### Requirement: Durable authoritative writes
The system SHALL validate, authorize, persist state, persist audit, then return success/failure for state-changing operations, and SHALL support idempotent retries via request_id.

#### Scenario: Idempotent retry
- GIVEN a reassignment request with request_id R1 succeeded
- WHEN the same request_id is submitted again
- THEN the system returns the original result without creating a duplicate active assignment
