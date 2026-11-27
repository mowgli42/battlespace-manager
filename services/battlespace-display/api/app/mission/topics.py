"""UCI Redis topics for battlespace-manager mission-management fan-out.

These live under ``uci.mission.*`` but intentionally avoid colliding with
o-my mission-*plan* topics (``uci.mission.plan``, ``uci.mission.plan.status``, …).

Until o-my pins the constants in ``uci_common.topics``, BM owns the names via
env overrides. Publishing is best-effort and never the sole authority for state.
"""

from __future__ import annotations

import os

# Umbrella + typed fan-out (JSON envelopes)
TOPIC_MISSION_EVENT = os.getenv("TOPIC_MISSION_EVENT", "uci.mission.event")
TOPIC_MISSION_TASK = os.getenv("TOPIC_MISSION_TASK", "uci.mission.task")
TOPIC_MISSION_ASSIGNMENT = os.getenv("TOPIC_MISSION_ASSIGNMENT", "uci.mission.assignment")
TOPIC_MISSION_OWNERSHIP = os.getenv("TOPIC_MISSION_OWNERSHIP", "uci.mission.ownership")
TOPIC_MISSION_ALERT = os.getenv("TOPIC_MISSION_ALERT", "uci.mission.alert")
TOPIC_MISSION_SAMPLE = os.getenv("TOPIC_MISSION_SAMPLE", "uci.mission.sample")

ALL_MISSION_TOPICS: tuple[str, ...] = (
    TOPIC_MISSION_EVENT,
    TOPIC_MISSION_TASK,
    TOPIC_MISSION_ASSIGNMENT,
    TOPIC_MISSION_OWNERSHIP,
    TOPIC_MISSION_ALERT,
    TOPIC_MISSION_SAMPLE,
)

SUBSCRIBE_TOPICS: tuple[str, ...] = (
    TOPIC_MISSION_EVENT,
    TOPIC_MISSION_TASK,
    TOPIC_MISSION_ASSIGNMENT,
    TOPIC_MISSION_OWNERSHIP,
    TOPIC_MISSION_ALERT,
    TOPIC_MISSION_SAMPLE,
)


def topic_for_event_type(event_type: str, entity_type: str) -> str:
    """Map audit/event types to a typed topic; always also publish umbrella event."""
    et = (event_type or "").lower()
    ent = (entity_type or "").lower()
    if "sample" in et or ent == "fleet":
        return TOPIC_MISSION_SAMPLE
    if ent == "task" or et.startswith("task."):
        return TOPIC_MISSION_TASK
    if ent == "assignment" or "assign" in et:
        return TOPIC_MISSION_ASSIGNMENT
    if ent == "platform" or "ownership" in et or "primary" in et or "support" in et or "commitment" in et:
        return TOPIC_MISSION_OWNERSHIP
    if ent == "alert" or et.startswith("alert."):
        return TOPIC_MISSION_ALERT
    return TOPIC_MISSION_EVENT
