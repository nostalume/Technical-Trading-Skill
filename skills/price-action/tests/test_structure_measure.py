# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline conformance tests for explicit B2 measurements, not trading signals."""

from __future__ import annotations

import copy
import json
import random
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure.py"
MODULE = runpy.run_path(str(SCRIPT))
calculate = MODULE["calculate"]
RequestError = MODULE["RequestError"]


def bar(bar_id, high, low, close=None, **metadata):
    return {
        "id": bar_id,
        "high": high,
        "low": low,
        "close": (high + low) / 2 if close is None else close,
        **metadata,
    }


def request(op, bars=None, **fields):
    result = {"schema_version": 1, "operation": op, **fields}
    if bars is not None:
        result.update(bars=bars, order="oldest_first")
    return result


def manual(price, label="given", **metadata):
    return {"price": price, "label": label, **metadata}


def ref(bar_id, field="close"):
    return {"bar_id": bar_id, "field": field}


def rr_request(**fields):
    return (
        request(
            "risk_reward",
            direction="long",
            entry=manual(100, "entry"),
            stop=manual(98, "stop"),
            targets=[manual(106, "target")],
        )
        | fields
    )


def pivot_bars():
    return [
        bar("a", 10, 0, closed=True, available_at_ms=10),
        bar("b", 12, 1, closed=True, available_at_ms=20),
        bar("c", 11, 0, closed=True, available_at_ms=30),
    ]


class WindowTests(unittest.TestCase):
    def test_window_arithmetic_and_extreme_sources(self):
        bars = [bar("a", 14, 8, 10), bar("b", 14, 9, 12), bar("c", 13, 8, 11)]
        r = calculate(request("window", bars))
        data, m = r["data"], r["data"]["metrics"]
        self.assertEqual((data["high_ids"], data["low_ids"]), (["a", "b"], ["a", "c"]))
        self.assertEqual(
            [
                m[k]["value"]
                for k in (
                    "high",
                    "low",
                    "width",
                    "distance_to_high",
                    "distance_to_low",
                    "net_close_change",
                )
            ],
            [14, 8, 6, 3, 3, 1],
        )
        self.assertEqual(m["last_close_position"]["value"], 0.5)
        self.assertAlmostEqual(m["overlap_mean"]["value"], (5 / 6 + 4 / 6) / 2)
        self.assertEqual(data["possible_pair_count"], 2)
        self.assertEqual(m["net_close_change"]["evidence"]["count"], 2)
        self.assertEqual(m["high"]["evidence"]["count"], 3)

    def test_two_observations_use_one_pair(self):
        r = calculate(request("window", [bar("a", 4, 0), bar("b", 6, 2)]))
        self.assertEqual(r["data"]["possible_pair_count"], 1)
        self.assertEqual(r["data"]["defined_pair_count"], 1)
        self.assertAlmostEqual(r["data"]["metrics"]["overlap_mean"]["value"], 1 / 3)

    def test_zero_pairs_excluded_with_visible_counts(self):
        r = calculate(request("window", [bar("a", 10, 10), bar("b", 10, 10), bar("c", 14, 8)]))
        data = r["data"]
        self.assertEqual(
            (
                data["defined_pair_count"],
                data["undefined_pair_count"],
                data["unavailable_pair_count"],
                data["possible_pair_count"],
            ),
            (1, 1, 0, 2),
        )
        self.assertEqual(data["metrics"]["overlap_mean"]["value"], 0)
        all_flat = calculate(request("window", [bar("a", 10, 10), bar("b", 10, 10)]))
        self.assertEqual(all_flat["data"]["metrics"]["overlap_mean"]["reason"], "no_defined_pairs")
        self.assertEqual(all_flat["data"]["metrics"]["last_close_position"]["reason"], "zero_range")

    def test_empty_and_single_windows(self):
        r = calculate(request("window", []))
        self.assertEqual(r["status"], "none")
        self.assertEqual(r["data"]["high_ids"], [])
        self.assertIsNone(r["data"]["metrics"]["high"]["value"])
        r = calculate(request("window", [bar("a", 0, -2)]))
        self.assertEqual(r["data"]["metrics"]["net_close_change"]["value"], 0)
        self.assertEqual(r["data"]["metrics"]["net_close_change"]["evidence"]["count"], 1)
        self.assertEqual(r["data"]["metrics"]["overlap_mean"]["reason"], "missing_pairs")

    def test_numeric_failure_not_silently_excluded(self):
        bars = [bar("a", 1.7e308, -1.7e308, 0), bar("b", 2, 0), bar("c", 3, 1)]
        r = calculate(request("window", bars))
        data = r["data"]
        self.assertEqual(data["unavailable_pair_count"], 1)
        self.assertEqual(data["defined_pair_count"], 1)
        self.assertEqual(data["metrics"]["overlap_mean"]["reason"], "numeric_range")
        json.dumps(r, allow_nan=False)

    def test_net_change_does_not_consume_middle_closure(self):
        bars = [
            bar("a", 10, 0, 5, closed=True, available_at_ms=1),
            bar("b", 10, 0, 5, closed=False),
            bar("c", 10, 0, 6, closed=True, available_at_ms=3),
        ]
        m = calculate(request("window", bars, as_of_ms=3))["data"]["metrics"]
        self.assertEqual(m["net_close_change"]["evidence"]["state"], "closed")
        self.assertEqual(
            m["net_close_change"]["evidence"]["timing"], "checked_declared_availability"
        )
        self.assertEqual(m["high"]["evidence"]["state"], "provisional")

    def test_affine_window_law(self):
        rng = random.Random(18)
        for _ in range(50):
            bars = [
                bar(str(i), lo + rng.randint(1, 20), lo)
                for i in range(7)
                for lo in [rng.randint(-50, 50)]
            ]
            scaled = [{**b, **{k: 2 * b[k] + 3 for k in ("high", "low", "close")}} for b in bars]
            a, b = (calculate(request("window", seq))["data"]["metrics"] for seq in (bars, scaled))
            self.assertAlmostEqual(
                a["last_close_position"]["value"], b["last_close_position"]["value"]
            )
            self.assertAlmostEqual(a["overlap_mean"]["value"], b["overlap_mean"]["value"])
            self.assertAlmostEqual(2 * a["width"]["value"], b["width"]["value"])


class CompareTests(unittest.TestCase):
    def test_explicit_past_reference_not_current_window(self):
        req = request(
            "compare",
            [bar("a", 14, 8), bar("b", 15, 9, 15), bar("future", 100, -100)],
            target_id="b",
            reference_ids=["a"],
        )
        r = calculate(req)
        m = r["data"]["metrics"]
        self.assertEqual(m["reference_high"]["value"], 14)
        self.assertEqual(m["high_delta"]["value"], 1)
        self.assertTrue(m["high_above_reference"]["value"])
        self.assertEqual(m["high_delta"]["evidence"]["count"], 2)
        prefix = calculate({**req, "bars": req["bars"][:2]})
        self.assertEqual(r["data"], prefix["data"])

    def test_reference_set_is_explicit_not_a_filled_interval(self):
        bars = [
            bar("a", 10, 0, closed=True, available_at_ms=1),
            bar("ignored", 100, -100, closed=False),
            bar("c", 12, -2, closed=True, available_at_ms=3),
            bar("d", 15, -3, closed=True, available_at_ms=4),
        ]
        r = calculate(request("compare", bars, target_id="d", reference_ids=["c", "a"], as_of_ms=4))
        m = r["data"]["metrics"]
        self.assertEqual(r["data"]["reference_ids"], ["c", "a"])
        self.assertEqual((m["reference_high"]["value"], m["reference_low"]["value"]), (12, -2))
        self.assertEqual(m["reference_high"]["evidence"]["count"], 2)
        self.assertEqual(m["high_delta"]["evidence"]["count"], 3)
        self.assertEqual(m["high_delta"]["evidence"]["state"], "closed")
        self.assertEqual(m["high_delta"]["evidence"]["timing"], "checked_declared_availability")

    def test_equal_and_two_sided_observations(self):
        r = calculate(
            request(
                "compare",
                [bar("a", 10, 0, 10), bar("b", 10, 0, 10)],
                target_id="b",
                reference_ids=["a"],
            )
        )
        for name in (
            "high_above_reference",
            "low_below_reference",
            "close_above_reference",
            "close_below_reference",
        ):
            self.assertFalse(r["data"]["metrics"][name]["value"])
        r = calculate(
            request(
                "compare", [bar("a", 10, 0), bar("b", 11, -1)], target_id="b", reference_ids=["a"]
            )
        )
        self.assertTrue(r["data"]["metrics"]["high_above_reference"]["value"])
        self.assertTrue(r["data"]["metrics"]["low_below_reference"]["value"])

    def test_reference_errors(self):
        for refs in (["b"], ["c"], ["none"], ["a", "a"], [], [True], [[]]):
            with self.subTest(refs=refs), self.assertRaises(RequestError):
                calculate(
                    request(
                        "compare",
                        [bar("a", 10, 0), bar("b", 11, 1), bar("c", 12, 2)],
                        target_id="b",
                        reference_ids=refs,
                    )
                )

    def test_order_and_overflow_preserve_strict_relations(self):
        req = request(
            "compare",
            [bar("a", -1e308, -1.5e308, -1e308), bar("b", 1.5e308, 1e308, 1e308)],
            target_id="b",
            reference_ids=["a"],
        )
        r = calculate(req)
        self.assertEqual(r["data"]["metrics"]["high_delta"]["reason"], "numeric_range")
        self.assertTrue(r["data"]["metrics"]["high_above_reference"]["value"])
        rev = calculate({**req, "bars": req["bars"][::-1], "order": "newest_first"})
        self.assertEqual(r["data"], rev["data"])


class PivotTests(unittest.TestCase):
    def test_confirmation_requires_right_observations(self):
        bars = pivot_bars()
        req = request("pivots", bars[:2], left=1, right=1, contiguous=True, as_of_ms=30)
        row = calculate(req)["data"]["rows"][1]
        self.assertEqual(row["confirmation"], "pending_right")
        self.assertTrue(row["metrics"]["high_so_far"]["value"])
        self.assertIsNone(row["confirmation_id"])
        self.assertIsNone(row["confirmation_at_ms"])
        row = calculate({**req, "bars": bars})["data"]["rows"][1]
        self.assertEqual(row["confirmation"], "confirmed")
        self.assertEqual(row["confirmation_id"], "c")
        self.assertEqual(row["confirmation_at_ms"], 30)
        self.assertEqual(row["metrics"]["high_so_far"]["evidence"]["count"], 3)

    def test_confirmation_is_window_phase_not_automatic_pivot(self):
        bars = [
            bar("a", 12, 0, closed=True),
            bar("b", 10, 1, closed=True),
            bar("c", 11, 0, closed=True),
        ]
        row = calculate(request("pivots", bars, left=1, right=1, contiguous=True))["data"]["rows"][
            1
        ]
        self.assertEqual(row["confirmation"], "confirmed")
        self.assertFalse(row["metrics"]["high_so_far"]["value"])
        self.assertFalse(row["metrics"]["low_so_far"]["value"])
        self.assertIsNone(row["confirmation_at_ms"])

    def test_closure_phase_includes_center_and_left(self):
        for index in range(3):
            for closed, phase in ((False, "provisional"), (None, "closure_unknown")):
                bars = pivot_bars()
                bars[index]["closed"] = closed
                with self.subTest(index=index, closed=closed):
                    row = calculate(request("pivots", bars, left=1, right=1, contiguous=True))[
                        "data"
                    ]["rows"][1]
                    self.assertEqual(row["confirmation"], phase)

    def test_equal_extreme_is_not_strict_pivot(self):
        bars = [bar("a", 12, 0), bar("b", 12, 0), bar("c", 11, 0)]
        row = calculate(request("pivots", bars, left=1, right=1, contiguous=True))["data"]["rows"][
            1
        ]
        self.assertFalse(row["metrics"]["high_so_far"]["value"])
        self.assertFalse(row["metrics"]["low_so_far"]["value"])

    def test_outside_center_can_be_both_extrema(self):
        bars = [bar("a", 10, 0), bar("b", 12, -2), bar("c", 11, -1)]
        row = calculate(request("pivots", bars, left=1, right=1, contiguous=True))["data"]["rows"][
            1
        ]
        self.assertTrue(row["metrics"]["high_so_far"]["value"])
        self.assertTrue(row["metrics"]["low_so_far"]["value"])

    def test_missing_left_and_unknown_continuity(self):
        r = calculate(request("pivots", pivot_bars(), left=1, right=1, contiguous=True))
        self.assertEqual(
            r["data"]["rows"][0]["metrics"]["high_so_far"]["reason"], "missing_left_neighbors"
        )
        self.assertEqual(r["data"]["rows"][-1]["confirmation"], "pending_right")
        r = calculate(request("pivots", pivot_bars(), left=1, right=1))
        self.assertEqual(r["status"], "none")
        for row in r["data"]["rows"]:
            self.assertEqual(row["confirmation"], "unavailable")
            self.assertIsNone(row["confirmation_id"])
            self.assertEqual(row["metrics"]["high_so_far"]["reason"], "continuity_unverified")

    def test_large_neighborhood_is_bounded_and_explicit(self):
        r = calculate(request("pivots", pivot_bars(), left=10**50, right=10**50, contiguous=True))
        self.assertEqual(r["status"], "none")
        r = calculate(request("pivots", pivot_bars(), left=1, right=10**50, contiguous=True))
        self.assertEqual(r["data"]["rows"][1]["confirmation"], "pending_right")
        self.assertEqual(r["data"]["rows"][1]["metrics"]["high_so_far"]["evidence"]["count"], 3)
        for key in ("left", "right"):
            for value in (0, -1, True, None, 1.5):
                req = request("pivots", pivot_bars(), left=1, right=1, contiguous=True) | {
                    key: value
                }
                with self.subTest(key=key, value=value), self.assertRaises(RequestError):
                    calculate(req)

    def test_completed_neighborhood_does_not_use_later_data(self):
        bars = pivot_bars()
        req = request("pivots", bars, left=1, right=1, contiguous=True, as_of_ms=40)
        expected = calculate(req)["data"]["rows"][1]
        later = calculate({**req, "bars": [*bars, bar("future", 100, -100, closed=False)]})
        self.assertEqual(later["data"]["rows"][1], expected)
        rev = calculate({**req, "bars": bars[::-1], "order": "newest_first"})
        self.assertEqual(rev["data"]["rows"][1], expected)

    def test_nonmonotonic_availability_max_and_missing(self):
        bars = pivot_bars()
        bars[0]["available_at_ms"] = 40
        row = calculate(request("pivots", bars, left=1, right=1, contiguous=True, as_of_ms=40))[
            "data"
        ]["rows"][1]
        self.assertEqual(row["confirmation_at_ms"], 40)
        bars[1].pop("available_at_ms")
        row = calculate(request("pivots", bars, left=1, right=1, contiguous=True, as_of_ms=40))[
            "data"
        ]["rows"][1]
        self.assertIsNone(row["confirmation_at_ms"])
        self.assertEqual(
            row["metrics"]["high_so_far"]["evidence"]["timing"], "availability_unverified"
        )


class ProjectionTests(unittest.TestCase):
    def test_explicit_range_projection(self):
        for direction, expected in (("up", 18), ("down", 10)):
            r = calculate(
                request(
                    "projection",
                    direction=direction,
                    anchor=manual(14),
                    basis={"type": "range", "low": manual(10), "high": manual(14)},
                )
            )
            self.assertEqual(r["data"]["metrics"]["height"]["value"], 4)
            self.assertEqual(r["data"]["metrics"]["target"]["value"], expected)
            self.assertEqual(r["status"], "complete")
            self.assertIn("projection_not_event_validation_or_target_probability", r["limitations"])
            self.assertEqual(r["data"]["metrics"]["height"]["evidence"]["count"], 0)

    def test_zero_range_is_visible_degeneracy(self):
        r = calculate(
            request(
                "projection",
                direction="up",
                anchor=manual(10),
                basis={"type": "range", "low": manual(10), "high": manual(10)},
            )
        )
        self.assertEqual(r["data"]["metrics"]["target"]["value"], 10)
        self.assertIn("degenerate_projection", r["limitations"])

    def test_move_order_direction_and_explicit_anchor(self):
        bars = [{"id": "a", "close": 10}, {"id": "b", "close": 14}, {"id": "c", "close": 15}]
        req = request(
            "projection",
            bars,
            direction="up",
            anchor=ref("c"),
            basis={"type": "move", "start": ref("a"), "end": ref("b")},
        )
        r = calculate(req)
        self.assertEqual(r["data"]["metrics"]["target"]["value"], 19)
        self.assertEqual(r["data"]["metrics"]["height"]["evidence"]["count"], 2)
        self.assertEqual(r["data"]["metrics"]["target"]["evidence"]["count"], 3)
        self.assertEqual(r["data"]["anchor"]["resolved_price"], 15)
        self.assertEqual(
            calculate({**req, "anchor": ref("b")})["data"]["metrics"]["target"]["value"], 18
        )
        for invalid in (
            {"direction": "down"},
            {"anchor": ref("a")},
            {"basis": {"type": "move", "start": ref("b"), "end": ref("a")}},
            {"basis": {"type": "move", "start": manual(10), "end": ref("b")}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(RequestError):
                calculate(req | invalid)
        manual_anchor = calculate(req | {"anchor": manual(15)})
        self.assertIn("manual_anchor_event_order_unverified", manual_anchor["limitations"])

    def test_down_move_and_invalid_range(self):
        bars = [{"id": "a", "close": 14}, {"id": "b", "close": 10}]
        r = calculate(
            request(
                "projection",
                bars,
                direction="down",
                anchor=ref("b"),
                basis={"type": "move", "start": ref("a"), "end": ref("b")},
            )
        )
        self.assertEqual(r["data"]["metrics"]["target"]["value"], 6)
        with self.assertRaises(RequestError):
            calculate(
                request(
                    "projection",
                    direction="up",
                    anchor=manual(14),
                    basis={"type": "range", "low": manual(14), "high": manual(10)},
                )
            )
        with self.assertRaises(RequestError):
            calculate(
                request(
                    "projection",
                    [{"id": "a", "close": 10}, {"id": "b", "close": 10}],
                    direction="up",
                    anchor=ref("b"),
                    basis={"type": "move", "start": ref("a"), "end": ref("b")},
                )
            )

    def test_numeric_overflow_has_no_target(self):
        r = calculate(
            request(
                "projection",
                direction="up",
                anchor=manual(0),
                basis={"type": "range", "low": manual(-1.7e308), "high": manual(1.7e308)},
            )
        )
        self.assertEqual(r["status"], "none")
        self.assertEqual(r["data"]["metrics"]["target"]["reason"], "numeric_range")
        json.dumps(r, allow_nan=False)


class RiskRewardTests(unittest.TestCase):
    def test_risk_reward_keeps_original_stop_and_target(self):
        req = rr_request()
        before = copy.deepcopy(req)
        r = calculate(req)
        m = r["data"]["targets"][0]["metrics"]
        self.assertEqual(
            [m[k]["value"] for k in ("risk_distance", "reward_distance", "reward_risk")], [2, 6, 3]
        )
        self.assertTrue(m["geometry_valid"]["value"])
        self.assertEqual(r["data"]["stop"]["price"], 98)
        self.assertEqual(r["data"]["targets"][0]["point"]["price"], 106)
        self.assertEqual(req, before)
        self.assertEqual(r["status"], "complete")

    def test_negative_reward_is_not_repaired(self):
        r = calculate(rr_request(targets=[manual(99)]))
        m = r["data"]["targets"][0]["metrics"]
        self.assertEqual(m["reward_distance"]["value"], -1)
        self.assertEqual(m["reward_risk"]["value"], -0.5)
        self.assertFalse(m["geometry_valid"]["value"])
        self.assertEqual(r["status"], "complete")

    def test_nonpositive_risk_and_explicit_direction(self):
        for stop in (100, 101):
            r = calculate(rr_request(stop=manual(stop)))
            m = r["data"]["targets"][0]["metrics"]
            self.assertEqual(m["reward_risk"]["reason"], "non_positive_risk")
            self.assertFalse(m["geometry_valid"]["value"])
        for direction in (None, "buy", "up", True):
            with self.subTest(direction=direction), self.assertRaises(RequestError):
                calculate(rr_request(direction=direction))

    def test_short_and_negative_prices(self):
        cases = [
            rr_request(direction="short", stop=manual(102), targets=[manual(94)]),
            rr_request(entry=manual(-10), stop=manual(-12), targets=[manual(-4)]),
        ]
        for req in cases:
            r = calculate(req)
            self.assertEqual(r["data"]["targets"][0]["metrics"]["reward_risk"]["value"], 3)

    def test_multiple_targets_independent_and_not_orders(self):
        r = calculate(rr_request(targets=[manual(106), manual(99)]))
        rows = r["data"]["targets"]
        self.assertEqual([t["metrics"]["reward_risk"]["value"] for t in rows], [3, -0.5])
        self.assertEqual([t["metrics"]["geometry_valid"]["value"] for t in rows], [True, False])
        for key in ("permission", "win_rate", "confidence", "filled", "order_status"):
            self.assertNotIn(key, r["data"])

    def test_point_provenance_deduplicates_ids_and_ignores_intervening(self):
        bars = [
            bar("a", 100, 98, 100, closed=True, available_at_ms=1),
            bar("ignored", 1000, -1000, closed=False),
            bar("c", 106, 106, 106, closed=True, available_at_ms=3),
        ]
        req = request(
            "risk_reward",
            bars,
            direction="long",
            entry=ref("a"),
            stop=ref("a", "low"),
            targets=[ref("c")],
            as_of_ms=3,
        )
        m = calculate(req)["data"]["targets"][0]["metrics"]
        self.assertEqual(m["risk_distance"]["evidence"]["count"], 1)
        self.assertEqual(m["reward_risk"]["evidence"]["count"], 2)
        self.assertEqual(m["reward_risk"]["evidence"]["state"], "closed")
        self.assertEqual(m["reward_risk"]["evidence"]["timing"], "checked_declared_availability")
        self.assertEqual(m["reward_risk"]["value"], 3)

    def test_manual_points_can_have_declared_times_but_not_closure(self):
        req = rr_request(
            as_of_ms=3,
            entry=manual(100, available_at_ms=1),
            stop=manual(98, available_at_ms=2),
            targets=[manual(106, available_at_ms=3)],
        )
        ev = calculate(req)["data"]["targets"][0]["metrics"]["reward_risk"]["evidence"]
        self.assertEqual(ev["count"], 0)
        self.assertEqual(ev["state"], "unknown")
        self.assertEqual(ev["available_at_ms"], 3)
        self.assertEqual(ev["timing"], "checked_declared_availability")
        req["stop"].pop("available_at_ms")
        ev = calculate(req)["data"]["targets"][0]["metrics"]["reward_risk"]["evidence"]
        self.assertIsNone(ev["available_at_ms"])
        self.assertEqual(ev["timing"], "availability_unverified")

    def test_point_errors_future_and_unused_bar_validation(self):
        invalid = [
            {"entry": manual(True)},
            {"entry": {"price": 100}},
            {"entry": {"price": 100, "label": ""}},
            {"entry": {"bar_id": "a", "field": "close", "price": 100}},
            {"entry": ref("absent")},
            {"targets": []},
            {"targets": None},
            {"entry": manual(100, available_at_ms=4), "as_of_ms": 3},
            {"bars": [], "order": None},
        ]
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(RequestError):
                calculate(rr_request(**fields))
        with self.assertRaises(RequestError):
            calculate(rr_request(bars=[bar("unused", 0, 1)], order="oldest_first"))
        with self.assertRaises(RequestError):
            calculate(
                rr_request(
                    bars=[bar("unused", 2, 1, available_at_ms=4)], order="oldest_first", as_of_ms=3
                )
            )
        with self.assertRaises(RequestError):
            calculate(
                request(
                    "risk_reward",
                    [{"id": "a", "close": 100}],
                    direction="long",
                    entry=ref("a", "open"),
                    stop=manual(98),
                    targets=[manual(106)],
                )
            )

    def test_overflow_does_not_become_zero_rr(self):
        r = calculate(
            rr_request(entry=manual(1.7e308), stop=manual(-1.7e308), targets=[manual(1.75e308)])
        )
        m = r["data"]["targets"][0]["metrics"]
        self.assertEqual(m["risk_distance"]["reason"], "numeric_range")
        self.assertEqual(m["reward_risk"]["reason"], "numeric_range")
        self.assertIsNone(m["reward_risk"]["value"])
        self.assertTrue(m["geometry_valid"]["value"])
        json.dumps(r, allow_nan=False)

    def test_affine_and_long_short_mirror_laws(self):
        rng = random.Random(23)
        for _ in range(50):
            e = rng.randint(-100, 100)
            s, t = e - rng.randint(1, 20), e + rng.randint(-20, 20)
            req = rr_request(entry=manual(e), stop=manual(s), targets=[manual(t)])
            a = calculate(req)["data"]["targets"][0]["metrics"]
            b = calculate(
                rr_request(
                    entry=manual(2 * e + 3), stop=manual(2 * s + 3), targets=[manual(2 * t + 3)]
                )
            )["data"]["targets"][0]["metrics"]
            reflected = calculate(
                rr_request(
                    direction="short", entry=manual(-e), stop=manual(-s), targets=[manual(-t)]
                )
            )["data"]["targets"][0]["metrics"]
            self.assertAlmostEqual(a["reward_risk"]["value"], b["reward_risk"]["value"])
            self.assertAlmostEqual(a["reward_risk"]["value"], reflected["reward_risk"]["value"])
            self.assertEqual(a["geometry_valid"]["value"], reflected["geometry_valid"]["value"])


class BoundaryTests(unittest.TestCase):
    def samples(self):
        return [
            request("window", pivot_bars()),
            request("compare", pivot_bars(), target_id="b", reference_ids=["a"]),
            request("pivots", pivot_bars(), left=1, right=1, contiguous=True),
            request(
                "projection",
                direction="up",
                anchor=manual(14),
                basis={"type": "range", "low": manual(10), "high": manual(14)},
            ),
            rr_request(),
        ]

    def test_all_operations_round_trip_independently_and_bounded(self):
        for req in self.samples():
            with self.subTest(operation=req["operation"]):
                command = [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "--max-input-bytes",
                    "10000",
                    "--max-output-bytes",
                    "100000",
                ]
                r = subprocess.run(
                    command,
                    input=json.dumps(req).encode(),
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stderr, b"")
                self.assertEqual(json.loads(r.stdout), calculate(req))
                tiny = subprocess.run(
                    [*command[:-1], "1"],
                    input=json.dumps(req).encode(),
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(tiny.returncode, 3)
                self.assertEqual(tiny.stdout, b"")
                self.assertEqual(json.loads(tiny.stderr)["code"], "output_budget_exceeded")

    def test_unknown_fields_and_request_purity(self):
        for req in self.samples():
            original = copy.deepcopy(req)
            calculate(req)
            self.assertEqual(req, original)
            with self.assertRaises(RequestError):
                calculate(req | {"min_rr": 1})
        for req in (request("window", []), request("pivots", [], left=1, right=1)):
            self.assertEqual(calculate(req)["status"], "none")
        with self.assertRaises(RequestError):
            calculate(request("window", [{"id": "a", "close": 1}]))

    def test_all_structure_operations_run_without_old_application(self):
        parent = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            self.assertEqual(Path(directory).resolve().parent, parent)
            target = Path(directory) / "measure.py"
            shutil.copyfile(SCRIPT, target)
            before = sorted(p.name for p in Path(directory).iterdir())
            for req in self.samples():
                r = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(target),
                        "--max-input-bytes",
                        "10000",
                        "--max-output-bytes",
                        "100000",
                    ],
                    input=json.dumps(req).encode(),
                    cwd=directory,
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout), calculate(req))
            self.assertEqual(before, sorted(p.name for p in Path(directory).iterdir()))

    def test_pending_confirmation_check_detects_premature_confirmation_mutation(self):
        globals_ = MODULE["calculate"].__globals__
        original = globals_["pivots"]

        def premature(req, evidence):
            rows = original(req, evidence)
            for row in rows:
                if row["confirmation"] == "pending_right":
                    row["confirmation"] = "confirmed"
            return rows

        with patch.dict(globals_, {"pivots": premature}), self.assertRaises(AssertionError):
            PivotTests(
                "test_confirmation_requires_right_observations"
            ).test_confirmation_requires_right_observations()


if __name__ == "__main__":
    unittest.main()
