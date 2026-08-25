"""o-my + o-my-sim uci_common must both import (pkgutil.extend_path)."""

from __future__ import annotations

import unittest


class UciCommonMergeTests(unittest.TestCase):
    def test_c2_platform_messages_import(self) -> None:
        from uci_common.platform_messages import parse_platform_status_xml

        self.assertTrue(callable(parse_platform_status_xml))

    def test_sim_scenario_clock_import(self) -> None:
        from uci_common.gulfwar_sim.messages import parse_scenario_clock_xml
        from uci_common.topics import TOPIC_SCENARIO_CLOCK

        self.assertEqual(TOPIC_SCENARIO_CLOCK, "uci.scenario.clock")
        self.assertTrue(callable(parse_scenario_clock_xml))

    def test_killchain_import(self) -> None:
        from uci_common.gw_messages import parse_killchain_xml
        from uci_common.topics import TOPIC_KILLCHAIN

        self.assertEqual(TOPIC_KILLCHAIN, "uci.killchain.state")
        self.assertTrue(callable(parse_killchain_xml))


if __name__ == "__main__":
    unittest.main()
