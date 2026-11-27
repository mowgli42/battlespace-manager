# Operator happy-path Gherkin

High-level scenarios for harness-mode displays and mission management. Tags `@check:<id>` match
IDs in each module’s feature checks (`ENTITY_FEATURE_CHECKS`,
`BATTLESPACE_FEATURE_CHECKS`, `RF_FEATURE_CHECKS`, `MISSION_FEATURE_CHECKS`).

| Display | Feature file | Executable verifier |
|---------|--------------|---------------------|
| entity-display | [`entity-display/c2-map-happy-path.feature`](entity-display/c2-map-happy-path.feature) | `scripts/verify-entity-display-features.py` |
| battlespace-display | [`battlespace-display/f2t2ea-tasking-happy-path.feature`](battlespace-display/f2t2ea-tasking-happy-path.feature) | `scripts/verify-battlespace-display-features.py` |
| rf-display | [`rf-display/emso-deconfliction-happy-path.feature`](rf-display/emso-deconfliction-happy-path.feature) | `scripts/verify-rf-display-features.py` |
| mission-management | [`mission-supervisor-foundation.feature`](mission-management/mission-supervisor-foundation.feature), [`resource-management-phase2.feature`](mission-management/resource-management-phase2.feature), [`performance-intelligence-phase3.feature`](mission-management/performance-intelligence-phase3.feature) | `scripts/verify-mission-management-features.py` |

Alignment (tags ↔ harness check IDs) is enforced by `scripts/check-gherkin-alignment.py`
as part of `./scripts/run-all-tests.sh`.
