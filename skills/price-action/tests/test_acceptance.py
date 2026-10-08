# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline bundle acceptance; no model adherence or trading-edge claim."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / "scripts" / "measure.py"))
calculate = MODULE["calculate"]
RequestError = MODULE["RequestError"]


def candle(bar_id="signal", close=103, **metadata):
    return {"id": bar_id, "open": 100, "high": 104, "low": 99, "close": close, **metadata}


def request(operation, **fields):
    return {"schema_version": 1, "operation": operation, **fields}


def point(price, label):
    return {"price": price, "label": label}


class AcceptanceBoundaryTests(unittest.TestCase):
    def test_old_candle_cutoffs_do_not_classify_or_gate_measurements(self):
        expected_metrics = {
            "range",
            "body",
            "upper_wick",
            "lower_wick",
            "direction",
            "body_ratio",
            "upper_wick_ratio",
            "lower_wick_ratio",
            "close_position",
        }
        # Cross old body/close-position cutoffs by a small explicitly chosen delta.
        # These are fixture values, not tolerances or new trading thresholds.
        for threshold in (0.25, 0.35, 0.65):
            for value in (threshold - 0.001, threshold, threshold + 0.001):
                with self.subTest(value=value):
                    req = request(
                        "geometry",
                        order="oldest_first",
                        features=["candle"],
                        bars=[{"id": "s", "open": 0, "high": 1, "low": 0, "close": value}],
                    )
                    result = calculate(req)
                    metrics = result["data"]["rows"][0]["metrics"]
                    self.assertEqual(set(metrics), expected_metrics)
                    self.assertEqual(result["status"], "complete")
                    self.assertEqual(metrics["body_ratio"]["value"], value)
                    self.assertEqual(metrics["close_position"]["value"], value)
                    self.assertEqual(metrics["direction"]["value"], "up")

    def test_same_candle_geometry_can_have_different_prior_boundary_events(self):
        geometry = request(
            "geometry",
            order="oldest_first",
            features=["candle"],
            bars=[candle()],
        )
        readings = [
            {"regime_hypothesis": "two_sided_range"},
            {"regime_hypothesis": "upward_leg"},
        ]
        results = [calculate(geometry | {"context": context}) for context in readings]
        self.assertEqual(results[0]["data"], results[1]["data"])
        crossings = []
        # Explicit prior envelopes differ; the signal OHLC is identical.
        for prior_high in (110, 102):
            req = request(
                "compare",
                order="oldest_first",
                target_id="signal",
                reference_ids=["prior"],
                bars=[{"id": "prior", "high": prior_high, "low": 95, "close": 100}, candle()],
            )
            result = calculate(req)
            metrics = result["data"]["metrics"]
            crossings.append(metrics["close_above_reference"]["value"])
            self.assertEqual(metrics["close_above_reference"]["evidence"]["count"], 2)
        self.assertEqual(crossings, [False, True])
        # This observes geometry and crossing, not the model's choice of action.

    def test_rr_across_one_is_arithmetic_without_hidden_policy_or_repricing(self):
        req = request(
            "risk_reward",
            direction="long",
            entry=point(100, "given entry"),
            stop=point(98, "given stop"),
            targets=[point(101.98, "nearby"), point(102, "equal"), point(102.02, "farther")],
        )
        before = copy.deepcopy(req)
        baseline = calculate(req)
        policy = calculate(req | {"context": {"min_rr": 1, "allow_trade": False}})
        self.assertEqual(baseline["data"], policy["data"])
        self.assertEqual(baseline["status"], "complete")
        self.assertEqual(req, before)
        self.assertEqual(baseline["data"]["stop"]["resolved_price"], 98)
        for target, expected in zip(baseline["data"]["targets"], (0.99, 1, 1.01), strict=True):
            metrics = target["metrics"]
            self.assertEqual(
                set(metrics),
                {"risk_distance", "reward_distance", "reward_risk", "geometry_valid"},
            )
            self.assertAlmostEqual(metrics["reward_risk"]["value"], expected)
            self.assertTrue(metrics["geometry_valid"]["value"])

    def test_missing_scales_leave_one_bar_geometry_available(self):
        req = request(
            "geometry",
            order="oldest_first",
            bars=[candle()],
            features=["candle", "ema", "atr"],
            context={"legacy_min_bars": 20},
        )
        before = copy.deepcopy(req)
        result = calculate(req)
        metrics = result["data"]["rows"][0]["metrics"]
        self.assertEqual(result["status"], "partial")
        self.assertEqual(metrics["range"]["value"], 5)
        self.assertEqual(metrics["body_ratio"]["value"], 0.6)
        for name in ("range_atr", "body_atr", "close_ema_distance", "ema_gap_count"):
            self.assertEqual(metrics[name]["status"], "unavailable")
            self.assertEqual(metrics[name]["reason"], "missing_indicator")
            self.assertIsNone(metrics[name]["value"])
        self.assertEqual(req, before)

    def test_pivot_version_cutoff_equality_missingness_and_later_confirmation(self):
        bars = [
            {
                "id": "left",
                "high": 10,
                "low": 5,
                "close": 8,
                "closed": True,
                "time_ms": 0,
                "available_at_ms": 10,
            },
            {
                "id": "center",
                "high": 12,
                "low": 6,
                "close": 11,
                "closed": True,
                "time_ms": 10,
                "available_at_ms": 20,
            },
            {
                "id": "right",
                "high": 11,
                "low": 6,
                "close": 10,
                "closed": True,
                "time_ms": 20,
                "available_at_ms": 30,
            },
        ]
        base = request("pivots", order="oldest_first", contiguous=True, left=1, right=1)
        early = calculate(base | {"bars": bars[:2], "as_of_ms": 20})["data"]["rows"][1]
        self.assertEqual(early["confirmation"], "pending_right")
        self.assertTrue(early["metrics"]["high_so_far"]["value"])
        self.assertIsNone(early["confirmation_at_ms"])
        for cutoff in (20, 29):
            with self.subTest(cutoff=cutoff), self.assertRaises(RequestError) as caught:
                calculate(base | {"bars": bars, "as_of_ms": cutoff})
            self.assertEqual(caught.exception.code, "future_evidence")
        exact = calculate(base | {"bars": bars, "as_of_ms": 30})["data"]["rows"][1]
        self.assertEqual(exact["confirmation"], "confirmed")
        self.assertEqual(exact["confirmation_at_ms"], 30)
        self.assertTrue(exact["metrics"]["high_so_far"]["value"])
        forming = copy.deepcopy(bars)
        forming[-1]["closed"] = False
        row = calculate(base | {"bars": forming, "as_of_ms": 30})["data"]["rows"][1]
        self.assertEqual(row["confirmation"], "provisional")
        missing = copy.deepcopy(bars)
        missing[-1].pop("available_at_ms")
        row = calculate(base | {"bars": missing, "as_of_ms": 20})["data"]["rows"][1]
        self.assertEqual(row["confirmation"], "confirmed")
        self.assertIsNone(row["confirmation_at_ms"])
        self.assertEqual(
            row["metrics"]["high_so_far"]["evidence"]["timing"], "availability_unverified"
        )
        revised = copy.deepcopy(bars)
        revised[0]["available_at_ms"] = 31
        with self.assertRaises(RequestError) as caught:
            calculate(base | {"bars": revised, "as_of_ms": 30})
        self.assertEqual(caught.exception.code, "future_evidence")


class BundleAcceptanceTests(unittest.TestCase):
    def check_resources(self, root):
        entry = (root / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = entry.split("---", 2)[1]
        # The current metadata is plain scalars. This is not a general YAML parser.
        fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
        self.assertEqual(set(fields), {"name", "description", "license"})
        self.assertEqual(fields["name"], "price-action")
        self.assertEqual(fields["license"], "AGPL-3.0-or-later")
        self.assertTrue(0 < len(fields["description"]) <= 1024)
        documents = sorted(root.rglob("*.md"))
        examples = []
        for path in documents:
            source = path.read_text(encoding="utf-8")
            self.assertTrue(source.isascii(), str(path))
            self.assertTrue(source.endswith("\n"), str(path))
            self.assertEqual(sum(line.startswith("```") for line in source.splitlines()) % 2, 0)
            for destination in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source):
                target = (path.parent / destination).resolve()
                self.assertTrue(target.is_relative_to(root), destination)
                self.assertTrue(target.is_file(), destination)
            for block in re.findall(r"```json\s*\n(.*?)\n```", source, re.DOTALL):
                examples.append(json.loads(block))
            # The README's first PowerShell example stores JSON in a here-string.
            for block in re.findall(r"\$payload = @'\s*\n(.*?)\n'@", source, re.DOTALL):
                examples.append(json.loads(block))
        return examples

    def assert_example(self, req, response):
        data, op = response["data"], req["operation"]
        self.assertEqual(response["operation"], op)
        if op == "geometry":
            metrics = data["rows"][0]["metrics"]
            if req["features"] == ["candle"]:
                self.assertEqual(metrics["range"]["value"], 6)
                self.assertAlmostEqual(metrics["body_ratio"]["value"], 1 / 3)
            else:
                self.assertEqual(metrics["bar_ema_relation"]["value"], "above")
                self.assertEqual(metrics["ema_gap_count"]["value"], 1)
                self.assertEqual(data["rows"][0]["ema_gap_extent"], "lower_bound")
        elif op == "ema":
            self.assertEqual([row["ema"]["value"] for row in data["rows"]], [None, 11, 13])
        elif op == "atr":
            self.assertEqual([row["atr"]["value"] for row in data["rows"]], [None, 2.5, 2.75])
        elif op == "window":
            self.assertEqual(data["metrics"]["width"]["value"], 5)
            self.assertEqual(data["possible_pair_count"], 2)
        elif op == "compare":
            self.assertTrue(data["metrics"]["high_above_reference"]["value"])
            self.assertFalse(data["metrics"]["close_above_reference"]["value"])
        elif op == "pivots":
            self.assertEqual(data["rows"][-1]["confirmation"], "pending_right")
            self.assertIsNone(data["rows"][-1]["confirmation_at_ms"])
        elif op == "projection":
            self.assertEqual(data["metrics"]["height"]["value"], 10)
            self.assertEqual(data["metrics"]["target"]["value"], 110)
        elif op == "risk_reward":
            self.assertEqual(data["stop"]["resolved_price"], 98)
            expected = [3] if len(req["targets"]) == 1 else [0.9, 1.1]
            for target, ratio in zip(data["targets"], expected, strict=True):
                self.assertAlmostEqual(target["metrics"]["reward_risk"]["value"], ratio)
        else:
            self.fail(f"No acceptance oracle for documented operation: {op}")

    def test_documented_examples_and_all_operations_in_detached_bundle(self):
        # Freeze the complete inventory BEFORE creating the owned nested temp root.
        # Tests consume the bundle too; copy them without recursively discovering temp files.
        files = [path for path in ROOT.rglob("*") if path.is_file()]
        snapshot = {
            path.relative_to(ROOT): hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        }
        parent = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix="acceptance-", dir=parent) as directory:
            root = Path(directory).resolve()
            self.assertEqual(root.parent, parent)
            for path in files:
                target = root / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            self.assertFalse((root / "pa_agent").exists())
            self.assertFalse((root / "pyproject.toml").exists())
            examples = self.check_resources(root)
            hlc = [
                {"id": str(i), "high": h, "low": low, "close": close}
                for i, (h, low, close) in enumerate(((3, 1, 2), (5, 2, 4), (6, 3, 5)))
            ]
            # ATR/window have no complete JSON example in prose. Supply independent
            # hand-calculated fixtures so the detached run exercises all eight operations.
            examples.extend(
                [
                    request("atr", order="oldest_first", bars=hlc, period=2),
                    request("window", order="oldest_first", bars=hlc),
                ]
            )
            self.assertEqual({req["operation"] for req in examples}, set(MODULE["OPERATIONS"]))
            for req in examples:
                with self.subTest(operation=req["operation"]):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            "-B",
                            str(root / "scripts" / "measure.py"),
                            "--max-input-bytes",
                            "10000",
                            "--max-output-bytes",
                            "100000",
                        ],
                        input=json.dumps(req).encode("utf-8"),
                        cwd=root,
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, b"")
                    self.assertTrue(result.stdout.endswith(b"\n"))
                    self.assert_example(req, json.loads(result.stdout))
            after = {
                path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, snapshot)
        self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
