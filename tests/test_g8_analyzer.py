from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "g8-analyzer" / "src"))

from g8_analyzer import calculate_match_rate, calculate_sub_score, evaluate_gear_tier, predict_potential


class G8AnalyzerTests(unittest.TestCase):
    def test_sub_scores_match_upstream_rules(self) -> None:
        self.assertEqual(calculate_sub_score("速度", "4"), 8.0)
        self.assertEqual(calculate_sub_score("暴击率", "5%"), 8.0)
        self.assertEqual(calculate_sub_score("生命力", "500"), 10.0)

    def test_tier_boundaries(self) -> None:
        self.assertEqual(evaluate_gear_tier(39.9), "过渡使用")
        self.assertEqual(evaluate_gear_tier(40), "差点及格")
        self.assertEqual(evaluate_gear_tier(70), "大毕业")

    def test_potential_and_match_rate(self) -> None:
        expected, maximum = predict_potential(
            40,
            9,
            [{"name": "速度", "value": "4"}, {"name": "暴击率", "value": "5%"}],
            "传说",
        )
        self.assertEqual(expected, 52.4)
        self.assertEqual(maximum, 56.0)
        rate, set_matched = calculate_match_rate(
            {"weights": {"速度": 5}, "sets": ["速度"]},
            None,
            [{"name": "速度", "value": "4"}],
            "速度套装",
        )
        self.assertTrue(set_matched)
        self.assertEqual(rate, 100.0)


if __name__ == "__main__":
    unittest.main()
