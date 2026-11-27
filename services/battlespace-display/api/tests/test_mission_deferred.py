"""Deferred stack: Redis uci.mission.* bus, JWT SSO, continuous sampler."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import jwt
from fastapi import HTTPException
from starlette.requests import Request

from app.mission.auth import (
    ActorContext,
    clear_jwks_cache_for_tests,
    parse_actor,
)
from app.mission.bus import (
    MissionBusPublisher,
    ingest_bus_message,
    set_publisher_for_tests,
)
from app.mission.sampler import (
    reset_sampler_for_tests,
    start_continuous_sampler,
    stop_continuous_sampler,
)
from app.mission.service import MissionService, reset_mission_service_for_tests
from app.mission.store import MissionStore
from app.mission.topics import TOPIC_MISSION_OWNERSHIP, TOPIC_MISSION_SAMPLE, topic_for_event_type

REPO_ROOT = Path(__file__).resolve().parents[4]
SEED = REPO_ROOT / "fixtures" / "mission-management-seed-v1.json"
SUPER = ActorContext(actor_id="OP-SUPER-1", role="mission_supervisor")


def _svc() -> MissionService:
    reset_mission_service_for_tests()
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = MissionStore(path)
    svc = MissionService(store)
    svc.ensure_seeded(SEED)
    return svc


def _request() -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    return Request(scope)


class TopicMappingTests(unittest.TestCase):
    def test_topic_mapping(self) -> None:
        self.assertEqual(topic_for_event_type("task.completed", "task"), "uci.mission.task")
        self.assertEqual(topic_for_event_type("platform.primary_set", "platform"), TOPIC_MISSION_OWNERSHIP)
        self.assertEqual(topic_for_event_type("analytics.sample_recorded", "fleet"), TOPIC_MISSION_SAMPLE)


class BusPublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pub = MissionBusPublisher(bus=None)
        set_publisher_for_tests(self.pub)
        os.environ.pop("MISSION_BUS_ENABLED", None)

    def tearDown(self) -> None:
        set_publisher_for_tests(None)

    def test_audit_publishes_envelope(self) -> None:
        svc = _svc()
        set_publisher_for_tests(self.pub)
        before = len(self.pub.published)
        svc.set_platform_primary(
            "COAL-E3-01",
            team_id="TEAM-AWACS",
            operator_id="OP-ALPHA",
            actor=SUPER,
            reason="bus-test",
        )
        self.assertGreater(len(self.pub.published), before)
        last = self.pub.published[-1]
        self.assertIn("uci.mission", last["topic"])
        self.assertEqual(last["envelope"]["schema"], "uci.mission.event/v1")
        self.assertTrue(last["envelope"]["event_id"])

    def test_sample_ingest_idempotent(self) -> None:
        svc = _svc()
        sample = {
            "sample_id": "US-TEST-1",
            "sampled_at": "2026-01-01T00:00:00Z",
            "platform_id": "COAL-E3-01",
            "technical_readiness": "Operational",
            "held_in_reserve": False,
            "committed": False,
            "scheduled_commitment": False,
            "mission_assigned": False,
            "stale": False,
            "source": "bus",
            "minutes_represented": 15,
        }
        body = json.dumps(
            {
                "event_id": "EVT-S1",
                "event_type": "analytics.sample_recorded",
                "entity_type": "fleet",
                "entity_id": "fleet",
                "actor_id": "peer",
                "payload": {"samples": [sample]},
            }
        )
        a1 = ingest_bus_message(svc.store, TOPIC_MISSION_SAMPLE, body)
        a2 = ingest_bus_message(svc.store, TOPIC_MISSION_SAMPLE, body)
        self.assertEqual(a1, "samples_added:1")
        self.assertEqual(a2, "samples_added:0")
        samples = svc.store.list_utilization_samples(platform_id="COAL-E3-01")
        self.assertTrue(any(s.get("sample_id") == "US-TEST-1" for s in samples))


class JwtAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_jwks_cache_for_tests()
        self.secret = "test-mission-jwt-secret-key-32b!"
        os.environ["MISSION_AUTH_MODE"] = "jwt"
        os.environ["MISSION_JWT_SECRET"] = self.secret
        os.environ["MISSION_JWT_ALGORITHMS"] = "HS256"
        os.environ.pop("MISSION_JWT_ISSUER", None)
        os.environ.pop("MISSION_JWT_AUDIENCE", None)
        os.environ.pop("MISSION_AUTH_ALLOW_HEADER_FALLBACK", None)

    def tearDown(self) -> None:
        os.environ["MISSION_AUTH_MODE"] = "header"
        for k in (
            "MISSION_JWT_SECRET",
            "MISSION_JWT_ALGORITHMS",
            "MISSION_AUTH_ALLOW_HEADER_FALLBACK",
            "MISSION_JWT_ISSUER",
            "MISSION_JWT_AUDIENCE",
        ):
            os.environ.pop(k, None)
        clear_jwks_cache_for_tests()

    def _token(self, **claims) -> str:
        payload = {
            "sub": "OP-SUPER-1",
            "role": "mission_supervisor",
            "exp": int(time.time()) + 3600,
            **claims,
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def test_bearer_jwt_authenticates(self) -> None:
        actor = asyncio.run(parse_actor(_request(), authorization=f"Bearer {self._token()}"))
        self.assertEqual(actor.actor_id, "OP-SUPER-1")
        self.assertEqual(actor.role, "mission_supervisor")
        self.assertEqual(actor.auth_source, "jwt")

    def test_jwt_mode_rejects_missing_token(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(parse_actor(_request()))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_header_fallback_when_enabled(self) -> None:
        os.environ["MISSION_AUTH_ALLOW_HEADER_FALLBACK"] = "1"
        actor = asyncio.run(
            parse_actor(_request(), x_actor_id="OP-ALPHA", x_actor_role="operator")
        )
        self.assertEqual(actor.actor_id, "OP-ALPHA")
        self.assertEqual(actor.auth_source, "header")


class SamplerTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_sampler_for_tests()
        os.environ.pop("MISSION_SAMPLER_ENABLED", None)
        os.environ.pop("MISSION_SAMPLER_INTERVAL_SECONDS", None)
        set_publisher_for_tests(None)

    def test_continuous_sampler_records_samples(self) -> None:
        svc = _svc()
        before = len(svc.store.list_utilization_samples())
        os.environ["MISSION_SAMPLER_ENABLED"] = "1"
        os.environ["MISSION_SAMPLER_INTERVAL_SECONDS"] = "5"
        pub = MissionBusPublisher(bus=None)
        set_publisher_for_tests(pub)

        start_continuous_sampler(lambda: svc, lambda: {})
        deadline = time.time() + 8
        while time.time() < deadline:
            if len(svc.store.list_utilization_samples()) > before:
                break
            time.sleep(0.2)
        stop_continuous_sampler()
        after = len(svc.store.list_utilization_samples())
        self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
