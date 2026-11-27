## ADDED Requirements

### Requirement: Single accountable owner
The system SHALL require exactly one accountable owner for every active task and track supporting operators separately.

#### Scenario: Task having one accountable owner
- GIVEN a task in status ASSIGNED or later (active)
- WHEN the task is persisted
- THEN accountable_owner_id is set to exactly one operator
- AND supporting_operator_ids does not include the accountable owner as a duplicate owner role

### Requirement: Reassignment acknowledgement
The system SHALL require the new accountable owner to acknowledge a reassignment before ownership transfer is finalized, unless an authorized administrative override is applied.

#### Scenario: Task reassignment awaiting acknowledgement
- GIVEN task T1 is owned by OP-ALPHA with status ACCEPTED
- WHEN a supervisor reassigns T1 to OP-BRAVO without override
- THEN a pending assignment is recorded with acknowledgement_status pending
- AND OP-ALPHA remains accountable until OP-BRAVO acknowledges
- AND prior assignment history is retained

### Requirement: Completion evidence
The system SHALL require configured completion evidence before marking a task COMPLETED.

#### Scenario: Task completion requiring evidence
- GIVEN task T1 has completion_criteria requiring evidence
- WHEN an owner attempts completion without evidence
- THEN the system rejects the transition
- AND when valid evidence is supplied the task becomes COMPLETED and an audit event is recorded

### Requirement: Unauthorized assignment changes
The system SHALL reject assignment and ownership mutations from unauthorized roles.

#### Scenario: Unauthorized assignment changes
- GIVEN actor role analyst
- WHEN the actor POSTs a task reassignment
- THEN the API returns 403
- AND no assignment state changes
