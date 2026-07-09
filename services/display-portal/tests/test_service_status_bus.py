"""Service status bus cache tests."""

from __future__ import annotations

import os
import sys
import unittest

_PORTAL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "display-portal"))
_OMY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "o-my", "packages", "uci_common", "src"))
for _p in (_PORTAL, _OMY):
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from service_status_bus import ServiceStatusCache  # noqa: E402
from uci_common.service_messages import ServiceStatusMsg, build_service_status_xml  # noqa: E402
from uci_common.topics import TOPIC_SERVICE_STATUS  # noqa: E402


class ServiceStatusBusTests(unittest.TestCase):
    def test_ingest_and_probe(self) -> None:
        cache = ServiceStatusCache()
        xml = build_service_status_xml(
            ServiceStatusMsg(name="entity-fusion", enabled=True, health="healthy", detail="heartbeat")
        )
        cache.ingest(TOPIC_SERVICE_STATUS, xml)
        probe = cache.probe_status("entity-fusion")
        self.assertIsNotNone(probe)
        assert probe is not None
        self.assertEqual(probe["status"], "live")
        self.assertEqual(probe["source"], "uci.service.status")


if __name__ == "__main__":
    unittest.main()
