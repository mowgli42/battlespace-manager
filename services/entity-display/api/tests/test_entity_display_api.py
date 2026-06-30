"""Entity display API logic tests."""
from __future__ import annotations

import unittest

from app.display_logic import build_feed_status_list, derive_affiliation


class DisplayLogicTests(unittest.TestCase):
    def test_derive_affiliation(self) -> None:
        self.assertEqual(derive_affiliation("Low", ["Commercial", "Non-Threat"]), "friendly")
        self.assertEqual(derive_affiliation("High", ["Alert"], "7700"), "hostile")
        self.assertEqual(derive_affiliation(None, []), "unknown")

    def test_feed_status_list(self) -> None:
        registry = [
            {"feed_id": "ads-b-sensor", "label": "ADS-B", "type": "sensor", "role": "entity"},
        ]
        ticks = {"ads-b-sensor": {"count": 3, "last_seen": 100.0}}
        feeds = build_feed_status_list(registry, ticks, now=110.0)
        self.assertEqual(feeds[0]["status"], "live")
        self.assertEqual(feeds[0]["message_count"], 3)


if __name__ == "__main__":
    unittest.main()
