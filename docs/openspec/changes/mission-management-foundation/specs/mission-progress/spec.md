## ADDED Requirements

### Requirement: Criteria-based mission progress
The system SHALL compute mission progress from defined task and milestone completion criteria and SHALL NOT infer mission completion solely from aircraft location, telemetry, or elapsed time.

#### Scenario: Supervisor viewing fleet-wide progress
- GIVEN a mission with required milestones and accountable tasks
- WHEN a supervisor requests mission progress
- THEN the response includes objectives, required milestones, completed/in-progress/blocked/deferred/overdue task counts, and upcoming deadlines
- AND progress percentages are derived only from milestone and task completion criteria
