## ADDED Requirements

### Requirement: Operator workload indicators without capacity score
The system SHALL present operator workload as explicit contributing factors (primary aircraft, supported aircraft, active tasks, pending acknowledgements, time-sensitive tasks, unresolved exceptions, availability state) and SHALL NOT expose an arbitrary 0–100% workload capacity score in Phase 1.

#### Scenario: Operator workload conflict
- GIVEN operator OP-ALPHA is primary on one platform and support on another
- AND OP-ALPHA has multiple active tasks and a pending acknowledgement
- WHEN a supervisor views operator workload
- THEN the system lists the contributing factors
- AND highlights a conflict indicator for overlapping primary/support load
- AND does not auto-reassign tasks based on any score
