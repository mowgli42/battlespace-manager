## ADDED Requirements

### Requirement: Primary team ownership
The system SHALL ensure each active platform has exactly one designated primary team and MAY have one designated primary operator.

#### Scenario: Operator supporting multiple aircraft
- GIVEN operator OP-ALPHA has primary responsibility for platform COAL-F16C-01
- AND OP-ALPHA has support responsibility for platform COAL-F15E-01
- WHEN ownership is queried
- THEN primary and support responsibilities are listed separately
- AND support does not transfer primary ownership of COAL-F15E-01

#### Scenario: Operator retaining primary aircraft responsibility
- GIVEN operator OP-ALPHA is primary on COAL-F16C-01
- WHEN OP-ALPHA is added as support on another platform
- THEN OP-ALPHA remains primary on COAL-F16C-01

### Requirement: Platform reserve vs committed
The system SHALL distinguish operational platforms that are fully committed from operational platforms held in reserve (uncommitted).

#### Scenario: Platform operational but fully committed
- GIVEN platform COAL-F16C-01 has technical readiness Operational
- AND the platform has an active commitment covering the requested window
- WHEN operational availability is evaluated
- THEN the platform is marked unavailable for additional commitment
- AND it is counted as committed, not uncommitted-operational

#### Scenario: Platform operational and held in reserve
- GIVEN platform COAL-KC135-01 has technical readiness Operational
- AND no active or scheduled commitment covers the platform
- AND the platform is marked reserved
- WHEN fleet metrics are computed
- THEN the platform contributes to uncommitted operational time
- AND it is not classified as inefficiently utilized solely for being reserved
