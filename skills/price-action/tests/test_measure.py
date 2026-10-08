# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline B1 conformance tests, runnable using only Python's standard library."""

from __future__ import annotations

import copy
import io
import json
import math
import random
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal, localcontext
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure.py"
MODULE = runpy.run_path(str(SCRIPT))
calculate = MODULE["calculate"]
parse_request = MODULE["parse_request"]
RequestError = MODULE["RequestError"]


def bar(bar_id="a", o=10, h=14, lo=8, c=12, **metadata):
    return {"id": bar_id, "open": o, "high": h, "low": lo, "close": c, **metadata}


def request(bars=None, op="geometry", **fields):
    return {
        "schema_version": 1,
        "operation": op,
        "order": "oldest_first",
        "bars": [bar()] if bars is None else bars,
        **fields,
    }


def metrics(response, index=-1):
    return response["data"]["rows"][index]["metrics"]


class GeometryTests(unittest.TestCase):
    def test_hand_calculation(self):
        result = calculate(request(features=["candle"]))
        m = metrics(result)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(
            [m[k]["value"] for k in ("range", "body", "upper_wick", "lower_wick")], [6, 2, 2, 2]
        )
        for k in ("body_ratio", "upper_wick_ratio", "lower_wick_ratio"):
            self.assertAlmostEqual(m[k]["value"], 1 / 3)
        self.assertAlmostEqual(m["close_position"]["value"], 2 / 3)
        self.assertEqual(m["direction"]["value"], "up")
        self.assertNotIn("trend_bull", json.dumps(result))

    def test_flat_and_supplied_atr_states_are_distinct(self):
        for value, status, reason in (
            (2, "ok", None),
            (0, "undefined", "zero_scale"),
            (-1, "invalid", "negative_atr"),
            (None, "unavailable", "missing_indicator"),
        ):
            with self.subTest(atr=value):
                r = calculate(
                    request(
                        [bar(o=10, h=10, lo=10, c=10)],
                        features=["candle", "atr"],
                        atr={"points": [{"bar_id": "a", "value": value}]},
                    )
                )
                m = metrics(r)
                self.assertEqual(m["range"]["value"], 0)
                self.assertEqual(m["body_ratio"]["status"], "undefined")
                self.assertEqual(
                    (m["range_atr"]["status"], m["range_atr"]["reason"]), (status, reason)
                )
                self.assertEqual(m["range_atr"]["value"], 0 if status == "ok" else None)

    def test_equal_range_not_mutually_exclusive(self):
        r = calculate(request([bar("a"), bar("b")], contiguous=True))
        m = metrics(r)
        for k in ("inside_prev_observed", "outside_prev_observed", "equal_range"):
            self.assertIs(m[k]["value"], True)
        self.assertEqual(m["ii"]["status"], "unavailable")
        self.assertEqual(metrics(r, 0)["inside_prev_observed"]["reason"], "missing_previous")

    def test_inside_sequences_and_ioi(self):
        ranges = [(0, 10), (1, 9), (0, 10), (2, 8)]
        bars = [bar(str(i), (lo + h) / 2, h, lo, (lo + h) / 2) for i, (lo, h) in enumerate(ranges)]
        m = metrics(calculate(request(bars, contiguous=True)))
        self.assertTrue(m["ioi"]["value"])
        self.assertFalse(m["ii"]["value"])
        equal = calculate(request([bar(str(i)) for i in range(4)], contiguous=True))
        for k in ("ii", "iii", "ioi"):
            self.assertTrue(metrics(equal)[k]["value"])

    def test_unknown_continuity_only_disables_continuous_measurements(self):
        r = calculate(request([bar("a"), bar("b")]))
        self.assertTrue(metrics(r)["inside_prev_observed"]["value"])
        self.assertEqual(metrics(r)["ii"]["reason"], "continuity_unverified")

    def test_overlap_is_intersection_over_envelope(self):
        r = calculate(request([bar("a", 2, 4, 0, 2), bar("b", 4, 6, 2, 4)]))
        self.assertAlmostEqual(metrics(r)["overlap_envelope_ratio"]["value"], 1 / 3)
        r = calculate(request([bar("a", 1, 1, 1, 1), bar("b", 1, 1, 1, 1)]))
        self.assertEqual(metrics(r)["overlap_envelope_ratio"]["reason"], "zero_envelope")
        r = calculate(request([bar("a", 0, 0, 0, 0), bar("b", 1, 1, 1, 1)]))
        self.assertEqual(metrics(r)["overlap_envelope_ratio"]["value"], 0)

    def test_local_output_retains_history(self):
        req = request([bar(str(i)) for i in range(5)], contiguous=True)
        full = calculate(req)
        partial = calculate({**req, "output_last": 1})
        self.assertEqual(partial["data"]["rows"], full["data"]["rows"][-1:])
        self.assertEqual(partial["input_ids"], full["input_ids"])
        self.assertEqual(partial["parameters"]["output_count"], 1)
        self.assertEqual(len(calculate({**req, "output_last": 100})["data"]["rows"]), 5)

    def test_input_direction_equivalence(self):
        req = request([bar(str(i), c=10 + i) for i in range(4)], contiguous=True)
        r = calculate(req)
        reversed_r = calculate({**req, "order": "newest_first", "bars": req["bars"][::-1]})
        self.assertEqual(r["data"], reversed_r["data"])
        self.assertEqual(r["input_ids"], reversed_r["input_ids"])

    def test_evidence_state_and_declared_time(self):
        bars = [
            bar("a", closed=False, available_at_ms=10),
            bar("b", closed=True, available_at_ms=20),
        ]
        r = calculate(request(bars, as_of_ms=20))
        ev = metrics(r)["inside_prev_observed"]["evidence"]
        self.assertEqual(ev["state"], "provisional")
        self.assertEqual(ev["available_at_ms"], 20)
        self.assertEqual(ev["timing"], "checked_declared_availability")
        self.assertEqual(metrics(r)["range"]["evidence"]["state"], "closed")
        no_cutoff = calculate(request(bars))
        self.assertEqual(
            metrics(no_cutoff)["range"]["evidence"]["timing"], "availability_unverified"
        )
        bars[0].pop("available_at_ms")
        self.assertIsNone(
            metrics(calculate(request(bars, as_of_ms=20)))["inside_prev_observed"]["evidence"][
                "available_at_ms"
            ]
        )

    def test_ema_gap_extent_and_missing_boundary(self):
        # Relative to E=0: touch, above, above, below, missing, below.
        bars = [
            bar("0", 0, 1, -1, 0),
            bar("1", 2, 3, 1, 2),
            bar("2", 2, 3, 1, 2),
            bar("3", -2, -1, -3, -2),
            bar("4", -2, -1, -3, -2),
            bar("5", -2, -1, -3, -2),
        ]
        req = request(
            bars,
            features=["ema"],
            contiguous=True,
            ema={
                "method": "test",
                "period": 1,
                "points": [{"bar_id": str(i), "value": 0} for i in (0, 1, 2, 3, 5)],
            },
        )
        rows = calculate(req)["data"]["rows"]
        self.assertEqual(
            [r["metrics"]["ema_gap_count"]["value"] for r in rows], [0, 1, 2, 1, None, 1]
        )
        self.assertEqual(
            [r["ema_gap_extent"] for r in rows],
            ["exact", "exact", "exact", "exact", None, "lower_bound"],
        )
        self.assertEqual(rows[2]["metrics"]["ema_gap_count"]["evidence"]["count"], 3)
        self.assertEqual(rows[3]["metrics"]["ema_gap_count"]["evidence"]["first_id"], "2")
        self.assertEqual(rows[5]["metrics"]["ema_gap_count"]["evidence"]["first_id"], "4")
        req["contiguous"] = None
        self.assertEqual(
            metrics(calculate(req))["ema_gap_count"]["reason"], "continuity_unverified"
        )

    def test_left_truncated_gap_is_lower_bound(self):
        req = request(
            [bar(str(i)) for i in range(3)],
            features=["ema"],
            contiguous=True,
            ema={"points": [{"bar_id": str(i), "value": 0} for i in range(3)]},
        )
        r = calculate(req)
        self.assertEqual(metrics(r)["ema_gap_count"]["value"], 3)
        self.assertEqual(r["data"]["rows"][-1]["ema_gap_extent"], "lower_bound")

    def test_input_not_mutated_and_context_not_policy(self):
        req = request(context={"features": ["atr"], "min_bars": 20, "direction": "sell"})
        before = copy.deepcopy(req)
        r = calculate(req)
        self.assertEqual(req, before)
        self.assertEqual(r["context"], req["context"])
        self.assertNotIn("range_atr", metrics(r))

    def test_numeric_overflow_is_not_clamped(self):
        r = calculate(request([bar(o=0, h=1.7e308, lo=-1.7e308, c=0)], features=["candle"]))
        self.assertEqual(metrics(r)["range"]["reason"], "numeric_range")
        self.assertEqual(metrics(r)["body_ratio"]["reason"], "numeric_range")
        self.assertEqual(metrics(r)["direction"]["value"], "flat")
        json.dumps(r, allow_nan=False)

    def test_affine_and_reflection_laws(self):
        rng = random.Random(20261008)
        for _ in range(100):
            lo = rng.randint(-100, 100)
            h = lo + rng.randint(1, 30)
            o, c = rng.randint(lo, h), rng.randint(lo, h)
            base = bar(o=o, h=h, lo=lo, c=c)
            m = metrics(calculate(request([base], features=["candle"])))
            transformed = {**base, **{k: 2 * base[k] + 3 for k in ("open", "high", "low", "close")}}
            moved = metrics(calculate(request([transformed], features=["candle"])))
            for k in ("body_ratio", "upper_wick_ratio", "lower_wick_ratio", "close_position"):
                self.assertAlmostEqual(m[k]["value"], moved[k]["value"])
            reflected = bar(o=-o, h=-lo, lo=-h, c=-c)
            rm = metrics(calculate(request([reflected], features=["candle"])))
            self.assertAlmostEqual(rm["upper_wick_ratio"]["value"], m["lower_wick_ratio"]["value"])
            self.assertAlmostEqual(rm["close_position"]["value"], 1 - m["close_position"]["value"])


class AdmissionTests(unittest.TestCase):
    def test_invalid_inputs(self):
        cases = [
            request([bar(h=7)]),
            request([bar(c=20)]),
            request([bar(o=True)]),
            request([bar(c="12")]),
            request([bar(c=None)]),
            request([bar(c=float("nan"))]),
            request([bar("a"), bar("a")]),
            request([bar(id=" ")]),
            request([bar(closed="true")]),
            request([bar(time_ms=True)]),
            request(order="auto"),
            request(contiguous=1),
            request(features=[]),
            request(features=["candle", "candle"]),
            request(features=[[]]),
            request(output_last=0),
            request(output_last=True),
            request(context=[]),
            request(extra=1),
            request(ema={}),
            request(op="pivots"),
            request(op="ema", period=True),
            request(op="atr", period=0),
            request(schema_version=True),
            request([bar(unknown=1)]),
            request([bar(c=10**400)]),
            request([bar(c=float("inf"))]),
            request(context={"bad": float("nan")}),
        ]
        for req in cases:
            with self.subTest(req=req), self.assertRaises(RequestError):
                calculate(req)

    def test_indicator_alignment_and_schema(self):
        for bundle in (
            {"points": [{"bar_id": "other", "value": 1}]},
            {"points": [{"bar_id": "a", "value": 1}] * 2},
            {"points": [{"bar_id": "a"}]},
            {"period": 0},
            {"method": ""},
            {"unknown": 1},
            {"points": None},
        ):
            with self.subTest(bundle=bundle), self.assertRaises(RequestError):
                calculate(request(features=["ema"], ema=bundle))

    def test_time_conflicts_and_future_evidence(self):
        cases = [
            request([bar("a", time_ms=2), bar("b"), bar("c", time_ms=1)]),
            request([bar(available_at_ms=21)], as_of_ms=20),
            request(
                features=["ema"],
                as_of_ms=20,
                ema={"points": [{"bar_id": "a", "value": 1, "available_at_ms": 21}]},
            ),
        ]
        for req in cases:
            with self.subTest(req=req), self.assertRaises(RequestError):
                calculate(req)

    def test_json_grammar(self):
        for raw in (
            b'{"a":1,"a":2}',
            b'{"context":{"a":1,"a":2}}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":1e400}',
            b'{"x":1e-400}',
            b'{"x":1e999999999999999999999999999999}',
            b"{} {}",
            b"\xef\xbb\xbf{}",
            b"\xff",
            b"{",
        ):
            with self.subTest(raw=raw), self.assertRaises(RequestError):
                parse_request(raw)
        self.assertEqual(parse_request(b'{"x":-0.0,"y":2e1}'), {"x": -0.0, "y": 20.0})
        self.assertEqual(parse_request(b'{"x":0e999999999999999999999999999999}'), {"x": 0.0})
        with self.assertRaises(RequestError):
            calculate(parse_request(json.dumps(request(context={"text": "\ud800"})).encode()))

    def test_empty_inputs_and_short_samples(self):
        for op in ("geometry", "ema", "atr"):
            req = request([], op, **({"period": 2} if op != "geometry" else {}))
            self.assertEqual(calculate(req)["status"], "none")
        self.assertEqual(calculate(request())["status"], "partial")


class IndicatorTests(unittest.TestCase):
    def test_hand_ema_and_atr(self):
        ema = calculate(
            request([{"id": str(i), "close": c} for i, c in enumerate((1, 2, 3))], "ema", period=2)
        )
        rows = ema["data"]["rows"]
        self.assertEqual(rows[0]["ema"]["reason"], "warmup")
        self.assertEqual([r["ema"]["value"] for r in rows], [None, 1.5, 2.5])
        bars = [
            {"id": str(i), "high": h, "low": lo, "close": c}
            for i, (h, lo, c) in enumerate(((3, 1, 2), (5, 2, 4), (6, 3, 5)))
        ]
        rows = calculate(request(bars, "atr", period=2))["data"]["rows"]
        self.assertEqual([r["true_range"]["value"] for r in rows], [2, 3, 3])
        self.assertEqual([r["atr"]["value"] for r in rows], [None, 2.5, 2.75])

    def test_zero_atr_and_huge_warmup_period(self):
        rows = calculate(request([bar(o=0, h=0, lo=0, c=0)], "atr", period=1))["data"]["rows"]
        self.assertEqual(rows[0]["atr"]["value"], 0)
        r = calculate(request([{"id": "a", "close": 1}], "ema", period=10**100))
        self.assertEqual(r["status"], "none")
        self.assertEqual(r["data"]["rows"][0]["ema"]["reason"], "warmup")

    def test_decimal_oracle(self):
        rng = random.Random(11)
        bars = []
        for i in range(100):
            lo = rng.randint(-100, 100) / 4
            h = lo + rng.randint(1, 20) / 4
            bars.append(bar(str(i), lo, h, lo, (h + lo) / 2))
        with localcontext() as ctx:
            ctx.prec = 60
            for op in ("ema", "atr"):
                for period in (1, 2, 7, 100):
                    rows = calculate(request(bars, op, period=period))["data"]["rows"]
                    values = [Decimal(b["close"]) for b in bars]
                    if op == "atr":
                        values = [
                            max(
                                Decimal(b["high"]) - Decimal(b["low"]),
                                abs(Decimal(b["high"]) - Decimal(bars[i - 1]["close"]))
                                if i
                                else Decimal(0),
                                abs(Decimal(b["low"]) - Decimal(bars[i - 1]["close"]))
                                if i
                                else Decimal(0),
                            )
                            for i, b in enumerate(bars)
                        ]
                    prev = sum(values[:period]) / period
                    for i in range(period - 1, len(bars)):
                        if i >= period:
                            if op == "ema":
                                alpha = Decimal(2) / (period + 1)
                                prev = alpha * values[i] + (1 - alpha) * prev
                            else:
                                prev = (prev * (period - 1) + values[i]) / period
                        self.assertTrue(
                            math.isclose(
                                rows[i][op]["value"], float(prev), rel_tol=1e-12, abs_tol=1e-12
                            )
                        )

    def test_prefix_invariance_and_order(self):
        bars = [bar(str(i), c=8 + i) for i in range(5)]
        for op in ("geometry", "ema", "atr"):
            kwargs = {} if op == "geometry" else {"period": 2}
            full = calculate(request(bars, op, **kwargs))
            prefix = calculate(request(bars[:3], op, **kwargs))
            rev = calculate(request(bars[::-1], op, order="newest_first", **kwargs))
            self.assertEqual(full["data"]["rows"][:3], prefix["data"]["rows"])
            self.assertEqual(full["data"], rev["data"])

    def test_smoothed_value_consumes_prefix_not_just_latest(self):
        bars = [
            bar("a", closed=False, available_at_ms=30),
            bar("b", closed=True, available_at_ms=20),
            bar("c", closed=True, available_at_ms=10),
        ]
        r = calculate(request(bars, "ema", period=2, as_of_ms=30))
        ev = r["data"]["rows"][-1]["ema"]["evidence"]
        self.assertEqual((ev["count"], ev["first_id"], ev["last_id"]), (3, "a", "c"))
        self.assertEqual(ev["available_at_ms"], 30)
        self.assertEqual(ev["state"], "provisional")

    def test_period_one_only_reports_actual_dependencies(self):
        bars = [
            bar("a", closed=False),
            bar("b", closed=True, available_at_ms=20),
            bar("c", closed=True, available_at_ms=30),
        ]
        for op, count, first in (("ema", 1, "c"), ("atr", 2, "b")):
            r = calculate(request(bars, op, period=1, as_of_ms=30))
            ev = r["data"]["rows"][-1][op]["evidence"]
            self.assertEqual((ev["count"], ev["first_id"], ev["state"]), (count, first, "closed"))
            self.assertEqual(ev["timing"], "checked_declared_availability")


class CliTests(unittest.TestCase):
    def invoke(self, payload, *extra, cwd=None, script=SCRIPT):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(script),
                "--max-input-bytes",
                "100000",
                "--max-output-bytes",
                "1000000",
                *extra,
            ],
            input=payload,
            capture_output=True,
            timeout=15,
            cwd=cwd,
            check=False,
        )

    def test_round_trip_and_no_chatter(self):
        completed = self.invoke(json.dumps(request([bar("café")])).encode())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        r = json.loads(completed.stdout)
        self.assertEqual(r["input_ids"], ["café"])
        self.assertEqual(r["status"], "partial")

    def test_budget_and_validation_failures(self):
        for extra, payload, code, exit_code in (
            (("--max-input-bytes", "1"), b"{}", "input_budget_exceeded", 3),
            (
                ("--max-output-bytes", "1"),
                json.dumps(request()).encode(),
                "output_budget_exceeded",
                3,
            ),
            ((), b"{", "invalid_json", 2),
            (("--max-input-bytes", "0"), b"{}", "invalid_budget", 2),
            (("--unknown",), b"{}", "invalid_request", 2),
            (("--max-input-bytes", "9" * 5000), b"{}", "invalid_budget", 2),
        ):
            with self.subTest(extra=extra):
                r = self.invoke(payload, *extra)
                self.assertEqual(r.returncode, exit_code, r.stderr)
                self.assertEqual(r.stdout, b"")
                self.assertEqual(json.loads(r.stderr)["code"], code)

    def test_help_and_required_budgets(self):
        r = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--help"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn(b"geometry", r.stdout)
        r = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            input=b"{}",
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, b"")

    def test_isolated_copy_and_no_files_written(self):
        parent = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            self.assertEqual(Path(directory).resolve().parent, parent)
            target = Path(directory) / "measure.py"
            shutil.copyfile(SCRIPT, target)
            # A hostile cwd config must not alter the request's calculation.
            config = Path(directory) / "config"
            config.mkdir()
            (config / "settings.json").write_text('{"min_bars":20}', encoding="utf-8")
            before = sorted(str(p.relative_to(directory)) for p in Path(directory).rglob("*"))
            r = self.invoke(
                json.dumps(request(features=["candle"])).encode(), cwd=directory, script=target
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(metrics(json.loads(r.stdout))["range"]["value"], 6)
            after = sorted(str(p.relative_to(directory)) for p in Path(directory).rglob("*"))
            self.assertEqual(before, after)

    def test_failure_and_cancellation_translation(self):
        class Input:
            def __init__(self):
                self.buffer = io.BytesIO(b"{}")

        class Output:
            def __init__(self):
                self.buffer = io.BytesIO()

        globals_ = MODULE["main"].__globals__
        args = ["--max-input-bytes", "100", "--max-output-bytes", "1000"]
        for fault, expected, code in (
            (KeyboardInterrupt(), 130, "interrupted"),
            (MemoryError(), 3, "resource_exhausted"),
            (RuntimeError("do not leak"), 1, "internal_error"),
        ):
            err = io.StringIO()
            with (
                patch.object(sys, "stdin", Input()),
                patch.object(sys, "stdout", Output()),
                patch.object(sys, "stderr", err),
                patch.dict(globals_, {"calculate": lambda _r, f=fault: throw(f)}),
            ):
                self.assertEqual(MODULE["main"](args), expected)
            self.assertEqual(json.loads(err.getvalue())["code"], code)
            self.assertNotIn("do not leak", err.getvalue())

    def test_stream_failure_is_not_success(self):
        class Input:
            buffer = io.BytesIO(json.dumps(request()).encode())

        class BrokenBuffer:
            def write(self, _data):
                raise OSError("stream closed")

        class Output:
            buffer = BrokenBuffer()

        err = io.StringIO()
        with (
            patch.object(sys, "stdin", Input()),
            patch.object(sys, "stdout", Output()),
            patch.object(sys, "stderr", err),
        ):
            result = MODULE["main"](["--max-input-bytes", "10000", "--max-output-bytes", "100000"])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(err.getvalue())["code"], "output_io_error")

    def test_input_is_read_with_a_byte_bound(self):
        class BoundedInput(io.BytesIO):
            def read(self, size=-1):
                self.size = size
                return super().read(size)

        class Input:
            buffer = BoundedInput(b"{}extra")

        class Output:
            buffer = io.BytesIO()

        err = io.StringIO()
        with (
            patch.object(sys, "stdin", Input()),
            patch.object(sys, "stdout", Output()),
            patch.object(sys, "stderr", err),
        ):
            result = MODULE["main"](["--max-input-bytes", "2", "--max-output-bytes", "100"])
        self.assertEqual(Input.buffer.size, 3)
        self.assertEqual(result, 3)
        self.assertEqual(Output.buffer.getvalue(), b"")


class MutationTests(unittest.TestCase):
    def test_equal_range_check_detects_a_strict_inside_mutation(self):
        globals_ = MODULE["calculate"].__globals__

        def wrong(current, prev):
            return current["high"] < prev["high"] and current["low"] > prev["low"]

        with patch.dict(globals_, {"inside": wrong}), self.assertRaises(AssertionError):
            GeometryTests(
                "test_equal_range_not_mutually_exclusive"
            ).test_equal_range_not_mutually_exclusive()


def throw(exception):
    raise exception


if __name__ == "__main__":
    unittest.main()
