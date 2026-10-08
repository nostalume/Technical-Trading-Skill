# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stateless price measurements: geometry, ema, atr, window, compare,
pivots, projection, risk_reward.

Only this CLI owns stdin/stdout. Calculations do not import the old application,
read files, fetch data, or decide whether a trade should be taken.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from itertools import pairwise

OPERATIONS = ("geometry", "ema", "atr", "window", "compare", "pivots", "projection", "risk_reward")
FEATURES = ("candle", "relations", "ema", "atr")
PRICES = ("open", "high", "low", "close")


class RequestError(ValueError):
    """A public admission failure, without user values in diagnostics."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code, self.path, self.message = code, path, message


def reject(code: str, path: str, message: str) -> None:
    raise RequestError(code, path, message)


def object_fields(value: object, allowed: set[str], path: str) -> dict:
    if not isinstance(value, dict) or value.keys() - allowed:
        reject("invalid_request", path, "Expected an object with declared fields only")
    return value


def integer(value: object, path: str, *, positive: bool = False, optional: bool = False):
    if value is None and optional:
        return None
    if type(value) is not int or (positive and value <= 0):
        reject("invalid_request", path, "Expected an integer in the declared domain")
    return value


def number(value: object, path: str) -> float:
    if type(value) not in (int, float):
        reject("invalid_request", path, "Expected a finite number, not a string or boolean")
    try:
        result = float(value)
    except OverflowError:
        reject("invalid_request", path, "Number outside finite binary64 range")
    if not math.isfinite(result):
        reject("invalid_request", path, "Number outside finite binary64 range")
    return result


def text_id(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        reject("invalid_request", path, "Expected a nonempty string")
    return value


def json_values(value: object) -> None:
    """Also validate context: ordinary JSON, finite numbers and encodable text."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                reject("invalid_request", "$", "JSON object keys must be strings")
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                reject("invalid_request", "$", "Text must be valid Unicode")
        elif type(item) in (int, float):
            number(item, "$")
        elif item is not None and type(item) is not bool:
            reject("invalid_request", "$", "Expected ordinary JSON values")


def parse_request(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                reject("invalid_json", "$", "Duplicate JSON key")
            result[key] = value
        return result

    def real(token):
        rounded = float(token)
        mantissa = token.lower().split("e", 1)[0]
        nonzero = any(digit in "123456789" for digit in mantissa)
        if not math.isfinite(rounded) or (nonzero and rounded == 0):
            reject("invalid_json", "$", "Number outside finite binary64 range")
        return rounded

    def constant(_token):
        reject("invalid_json", "$", "Non-JSON numeric constant")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=real,
            parse_constant=constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, RequestError):
            raise
        reject("invalid_json", "$", "Expected one UTF-8 JSON object without BOM")


def admit_point(
    value: object, bars: list[dict], by_id: dict, as_of, path: str, *, reference_only: bool = False
) -> dict:
    """Resolve an explicit price source, never guess a structure or quotation tick."""
    if isinstance(value, dict) and "bar_id" in value:
        source = object_fields(value, {"bar_id", "field"}, path)
        bar_id = text_id(source.get("bar_id"), path + ".bar_id")
        field = source.get("field")
        if bar_id not in by_id or field not in PRICES:
            reject("invalid_reference", path, "Unknown price reference")
        index = by_id[bar_id]
        if field not in bars[index]:
            reject("invalid_reference", path, "Referenced price field was not provided")
        return {
            "source": dict(source),
            "price": bars[index][field],
            "index": index,
            "available_at_ms": bars[index]["available_at_ms"],
        }
    if reference_only:
        reject("invalid_reference", path, "This operation requires an observation reference")
    source = object_fields(value, {"price", "label", "available_at_ms"}, path)
    price = number(source.get("price"), path + ".price")
    text_id(source.get("label"), path + ".label")
    available = integer(source.get("available_at_ms"), path + ".available_at_ms", optional=True)
    if as_of is not None and available is not None and available > as_of:
        reject("future_evidence", path + ".available_at_ms", "Evidence exceeds observation cutoff")
    return {"source": dict(source), "price": price, "index": None, "available_at_ms": available}


def admit(request: dict) -> dict:
    json_values(request)
    if not isinstance(request, dict):
        reject("invalid_request", "$", "Expected a request object")
    version = request.get("schema_version")
    if type(version) is not int or version != 1:
        reject("unsupported_version", "schema_version", "Supported version is 1")
    op = request.get("operation")
    if op not in OPERATIONS:
        reject("unsupported_operation", "operation", "Unsupported measurement operation")
    common = {"schema_version", "operation", "context", "as_of_ms", "bars", "order", "contiguous"}
    extra = {
        "geometry": {"features", "output_last", "ema", "atr"},
        "ema": {"period"},
        "atr": {"period"},
        "window": set(),
        "compare": {"target_id", "reference_ids"},
        "pivots": {"left", "right"},
        "projection": {"basis", "anchor", "direction"},
        "risk_reward": {"direction", "entry", "stop", "targets"},
    }[op]
    object_fields(request, common | extra, "$")
    context = request.get("context", {})
    if not isinstance(context, dict):
        reject("invalid_request", "context", "Expected a context object")
    as_of = integer(request.get("as_of_ms"), "as_of_ms", optional=True)
    contiguous = request.get("contiguous")
    if contiguous is not None and type(contiguous) is not bool:
        reject("invalid_request", "contiguous", "Expected boolean or null")
    order = request.get("order")
    scalar = op in ("projection", "risk_reward")
    if (not scalar or "bars" in request or "order" in request) and order not in (
        "oldest_first",
        "newest_first",
    ):
        reject("invalid_request", "order", "Explicit observation order required")
    raw_bars = request.get("bars", [] if scalar else None)
    if not isinstance(raw_bars, list):
        reject("invalid_request", "bars", "Expected an array")
    required = (
        ()
        if scalar
        else (PRICES if op == "geometry" else (("close",) if op == "ema" else PRICES[1:]))
    )
    bars, ids = [], set()
    for i, item in enumerate(raw_bars):
        path = f"bars[{i}]"
        object_fields(item, {*PRICES, "id", "closed", "time_ms", "available_at_ms"}, path)
        bar = dict(item)
        bar_id = text_id(bar.get("id"), path + ".id")
        if bar_id in ids:
            reject("invalid_bar", path + ".id", "Duplicate observation identity")
        ids.add(bar_id)
        for key in PRICES:
            if key in bar or key in required:
                bar[key] = number(bar.get(key), path + "." + key)
        if "high" in bar and "low" in bar and bar["high"] < bar["low"]:
            reject("invalid_bar", path, "High must not be below low")
        for key in ("open", "close"):
            if key in bar and (
                ("high" in bar and bar[key] > bar["high"])
                or ("low" in bar and bar[key] < bar["low"])
            ):
                reject("invalid_bar", path + "." + key, "Price outside provided bounds")
        bar["closed"] = bar.get("closed")
        if bar["closed"] is not None and type(bar["closed"]) is not bool:
            reject("invalid_bar", path + ".closed", "Expected boolean or null")
        for key in ("time_ms", "available_at_ms"):
            bar[key] = integer(bar.get(key), path + "." + key, optional=True)
        if (
            as_of is not None
            and bar["available_at_ms"] is not None
            and bar["available_at_ms"] > as_of
        ):
            reject(
                "future_evidence", path + ".available_at_ms", "Evidence exceeds observation cutoff"
            )
        bars.append(bar)
    if order == "newest_first":
        bars.reverse()
    previous_time = None
    for bar in bars:
        if bar["time_ms"] is not None:
            if previous_time is not None and bar["time_ms"] <= previous_time:
                reject("invalid_bar", "bars", "Known times contradict declared order")
            previous_time = bar["time_ms"]
    result = {
        "operation": op,
        "bars": bars,
        "context": context,
        "as_of_ms": as_of,
        "contiguous": contiguous,
        "order": order,
    }
    by_id = {bar["id"]: i for i, bar in enumerate(bars)}
    if op in ("ema", "atr"):
        result["period"] = integer(request.get("period"), "period", positive=True)
        return result
    if op == "window":
        return result
    if op == "compare":
        target = text_id(request.get("target_id"), "target_id")
        references = request.get("reference_ids")
        if (
            not isinstance(references, list)
            or not references
            or any(not isinstance(ref, str) or not ref.strip() for ref in references)
            or len(set(references)) != len(references)
        ):
            reject(
                "invalid_reference",
                "reference_ids",
                "Explicit unique reference identities required",
            )
        if target not in by_id or any(ref not in by_id for ref in references):
            reject("invalid_reference", "target_id/reference_ids", "Unknown observation identity")
        target_index = by_id[target]
        indexes = [by_id[ref] for ref in references]
        if any(index >= target_index for index in indexes):
            reject(
                "invalid_reference", "reference_ids", "References must strictly precede the target"
            )
        result.update(
            target_index=target_index,
            reference_indexes=indexes,
            target_id=target,
            reference_ids=list(references),
        )
        return result
    if op == "pivots":
        result["left"] = integer(request.get("left"), "left", positive=True)
        result["right"] = integer(request.get("right"), "right", positive=True)
        return result
    if scalar:
        direction = request.get("direction")
        allowed = ("up", "down") if op == "projection" else ("long", "short")
        if direction not in allowed:
            reject("invalid_request", "direction", "Explicit supported direction required")
        result["direction"] = direction
        if op == "risk_reward":
            result["entry"] = admit_point(request.get("entry"), bars, by_id, as_of, "entry")
            result["stop"] = admit_point(request.get("stop"), bars, by_id, as_of, "stop")
            targets = request.get("targets")
            if not isinstance(targets, list) or not targets:
                reject("invalid_request", "targets", "At least one explicit target required")
            result["targets"] = [
                admit_point(point, bars, by_id, as_of, f"targets[{i}]")
                for i, point in enumerate(targets)
            ]
        else:
            anchor = admit_point(request.get("anchor"), bars, by_id, as_of, "anchor")
            basis = request.get("basis")
            if not isinstance(basis, dict) or basis.get("type") not in ("range", "move"):
                reject("invalid_request", "basis", "Explicit range or move basis required")
            kind = basis["type"]
            names = ("low", "high") if kind == "range" else ("start", "end")
            object_fields(basis, {"type", *names}, "basis")
            points = [
                admit_point(
                    basis.get(name),
                    bars,
                    by_id,
                    as_of,
                    "basis." + name,
                    reference_only=kind == "move",
                )
                for name in names
            ]
            first, last = points
            if kind == "range":
                if last["price"] < first["price"]:
                    reject("invalid_request", "basis", "Range high must not be below low")
            else:
                if first["index"] >= last["index"]:
                    reject("invalid_reference", "basis", "Move start must precede end")
                if (
                    last["price"] <= first["price"]
                    if direction == "up"
                    else last["price"] >= first["price"]
                ):
                    reject("invalid_request", "basis", "Move prices contradict selected direction")
                if anchor["index"] is not None and anchor["index"] < last["index"]:
                    reject("invalid_reference", "anchor", "Move anchor must not precede its end")
            result.update(
                anchor=anchor, basis={"type": kind, **dict(zip(names, points, strict=True))}
            )
        return result
    features = request.get("features", ["candle", "relations"])
    if (
        not isinstance(features, list)
        or not features
        or any(not isinstance(f, str) or f not in FEATURES for f in features)
        or len(set(features)) != len(features)
    ):
        reject("invalid_request", "features", "Expected unique supported feature names")
    result["features"] = features
    result["output_last"] = (
        integer(request["output_last"], "output_last", positive=True)
        if "output_last" in request
        else None
    )
    for name in ("ema", "atr"):
        if name in request and name not in features:
            reject("invalid_request", name, "Indicator provided without selecting its feature")
        if name not in features:
            continue
        bundle = object_fields(request.get(name, {}), {"method", "period", "points"}, name)
        method = bundle.get("method")
        if method is not None:
            text_id(method, name + ".method")
        period = integer(bundle.get("period"), name + ".period", positive=True, optional=True)
        points = bundle.get("points", [])
        if not isinstance(points, list):
            reject("invalid_request", name + ".points", "Expected an array")
        aligned = {}
        for i, item in enumerate(points):
            path = f"{name}.points[{i}]"
            object_fields(item, {"bar_id", "value", "available_at_ms"}, path)
            bar_id = text_id(item.get("bar_id"), path + ".bar_id")
            if bar_id not in ids or bar_id in aligned:
                reject(
                    "invalid_reference", path + ".bar_id", "Unknown or duplicate indicator identity"
                )
            if "value" not in item:
                reject("invalid_request", path + ".value", "Explicit value or null required")
            value = None if item["value"] is None else number(item["value"], path + ".value")
            available = integer(
                item.get("available_at_ms"), path + ".available_at_ms", optional=True
            )
            if as_of is not None and available is not None and available > as_of:
                reject(
                    "future_evidence",
                    path + ".available_at_ms",
                    "Evidence exceeds observation cutoff",
                )
            aligned[bar_id] = {"value": value, "available_at_ms": available}
        result[name] = {"method": method, "period": period, "points": aligned}
    return result


class Evidence:
    """Prefix summaries avoid quadratic provenance for recursively smoothed values."""

    def __init__(self, bars: list[dict], as_of: int | None):
        self.bars, self.as_of = bars, as_of
        self.false, self.unknown, self.missing, self.latest = [0], [0], [0], [None]
        for bar in bars:
            self.false.append(self.false[-1] + (bar["closed"] is False))
            self.unknown.append(self.unknown[-1] + (bar["closed"] is None))
            time = bar["available_at_ms"]
            self.missing.append(self.missing[-1] + (time is None))
            known = [v for v in (self.latest[-1], time) if v is not None]
            self.latest.append(max(known) if known else None)

    def span(self, start: int, end: int) -> dict:
        if end < start:
            return self.selected([])
        provisional = self.false[end + 1] - self.false[start]
        unknown = self.unknown[end + 1] - self.unknown[start]
        missing = self.missing[end + 1] - self.missing[start]
        if missing:
            available = None
        elif start == 0:
            available = self.latest[end + 1]
        else:
            # Local geometry spans are bounded; pivot spans follow explicit neighborhoods.
            available = max(self.bars[i]["available_at_ms"] for i in range(start, end + 1))
        return {
            "first_id": self.bars[start]["id"],
            "last_id": self.bars[end]["id"],
            "count": end - start + 1,
            "state": "provisional" if provisional else ("unknown" if unknown else "closed"),
            "available_at_ms": available,
            "timing": "checked_declared_availability"
            if self.as_of is not None and available is not None
            else "availability_unverified",
        }

    def indicator(self, index: int, point: dict | None) -> dict:
        evidence = self.span(index, index)
        time = point["available_at_ms"] if point is not None else None
        if time is None or evidence["available_at_ms"] is None:
            evidence["available_at_ms"] = None
            evidence["timing"] = "availability_unverified"
        else:
            evidence["available_at_ms"] = max(evidence["available_at_ms"], time)
        return evidence

    def selected(self, indexes, manual_times=()) -> dict:
        """Summarize actual discrete dependencies, not every intervening observation."""
        indexes = set(indexes)
        states = [self.bars[i]["closed"] for i in indexes]
        times = [self.bars[i]["available_at_ms"] for i in indexes]
        times.extend(manual_times)
        if manual_times:
            states.append(None)
        available = max(times) if times and None not in times else None
        return {
            "first_id": self.bars[min(indexes)]["id"] if indexes else None,
            "last_id": self.bars[max(indexes)]["id"] if indexes else None,
            "count": len(indexes),
            "state": "provisional"
            if any(s is False for s in states)
            else ("unknown" if not states or any(s is None for s in states) else "closed"),
            "available_at_ms": available,
            "timing": "checked_declared_availability"
            if self.as_of is not None and available is not None
            else "availability_unverified",
        }

    def points(self, points: list[dict]) -> dict:
        return self.selected(
            [p["index"] for p in points if p["index"] is not None],
            [p["available_at_ms"] for p in points if p["index"] is None],
        )


def join_evidence(older: dict, newer: dict) -> dict:
    """Combine disjoint, adjacent consumption spans for a running EMA gap count."""
    states = (older["state"], newer["state"])
    times = (older["available_at_ms"], newer["available_at_ms"])
    return {
        "first_id": older["first_id"],
        "last_id": newer["last_id"],
        "count": older["count"] + newer["count"],
        "state": "provisional"
        if "provisional" in states
        else ("unknown" if "unknown" in states else "closed"),
        "available_at_ms": None if None in times else max(times),
        "timing": "checked_declared_availability"
        if all(e["timing"] == "checked_declared_availability" for e in (older, newer))
        else "availability_unverified",
    }


def metric(value: object, evidence: dict, status: str = "ok", reason: str | None = None):
    if status == "ok" and isinstance(value, float) and not math.isfinite(value):
        value, status, reason = None, "unavailable", "numeric_range"
    return {
        "value": value if status == "ok" else None,
        "status": status,
        "reason": reason,
        "evidence": evidence,
    }


def ratio(numerator: float, denominator: float, evidence: dict, reason: str) -> dict:
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return metric(None, evidence, "unavailable", "numeric_range")
    if denominator == 0:
        return metric(None, evidence, "undefined", reason)
    return metric(numerator / denominator, evidence)


def inside(current: dict, previous: dict) -> bool:
    return current["high"] <= previous["high"] and current["low"] >= previous["low"]


def outside(current: dict, previous: dict) -> bool:
    return current["high"] >= previous["high"] and current["low"] <= previous["low"]


def geometry(req: dict, evidence: Evidence) -> list[dict]:
    bars, features, rows = req["bars"], req["features"], []
    previous_side, previous_ema_evidence = None, None
    gap_count, gap_extent, gap_evidence = 0, None, None
    for i, bar in enumerate(bars):
        ev = evidence.span(i, i)
        o, h, lo, c = (bar[k] for k in PRICES)
        width, body = h - lo, abs(c - o)
        metrics = {}
        row = {"id": bar["id"], "metrics": metrics}
        if "candle" in features:
            upper, lower = h - max(o, c), min(o, c) - lo
            lengths = {"range": width, "body": body, "upper_wick": upper, "lower_wick": lower}
            metrics.update({name: metric(value, ev) for name, value in lengths.items()})
            metrics["direction"] = metric("up" if c > o else ("down" if c < o else "flat"), ev)
            for name in ("body", "upper_wick", "lower_wick"):
                metrics[name + "_ratio"] = ratio(lengths[name], width, ev, "zero_range")
            metrics["close_position"] = ratio(c - lo, width, ev, "zero_range")
        if "relations" in features:
            row["prev_observed_id"] = bars[i - 1]["id"] if i else None
            names = (
                "inside_prev_observed",
                "outside_prev_observed",
                "equal_range",
                "overlap_envelope_ratio",
                "high_delta_prev",
                "low_delta_prev",
            )
            if not i:
                metrics.update(
                    {name: metric(None, ev, "unavailable", "missing_previous") for name in names}
                )
            else:
                prev, pair_ev = bars[i - 1], evidence.span(i - 1, i)
                metrics["inside_prev_observed"] = metric(inside(bar, prev), pair_ev)
                metrics["outside_prev_observed"] = metric(outside(bar, prev), pair_ev)
                metrics["equal_range"] = metric(h == prev["high"] and lo == prev["low"], pair_ev)
                overlap = max(0.0, min(h, prev["high"]) - max(lo, prev["low"]))
                envelope = max(h, prev["high"]) - min(lo, prev["low"])
                metrics["overlap_envelope_ratio"] = ratio(
                    overlap, envelope, pair_ev, "zero_envelope"
                )
                metrics["high_delta_prev"] = metric(h - prev["high"], pair_ev)
                metrics["low_delta_prev"] = metric(lo - prev["low"], pair_ev)
            for name, relations in (
                ("ii", (inside, inside)),
                ("iii", (inside, inside, inside)),
                ("ioi", (inside, outside, inside)),
            ):
                start = max(0, i - len(relations))
                seq_ev = evidence.span(start, i)
                if req["contiguous"] is not True:
                    metrics[name] = metric(None, seq_ev, "unavailable", "continuity_unverified")
                elif i < len(relations):
                    metrics[name] = metric(None, seq_ev, "unavailable", "missing_neighbors")
                else:
                    value = all(
                        check(bars[start + j + 1], bars[start + j])
                        for j, check in enumerate(relations)
                    )
                    metrics[name] = metric(value, seq_ev)
        if "ema" in features:
            point = req["ema"]["points"].get(bar["id"])
            ema = point["value"] if point else None
            ema_ev = evidence.indicator(i, point)
            if ema is None:
                for name in (
                    "close_ema_relation",
                    "bar_ema_relation",
                    "close_ema_distance",
                    "ema_gap_count",
                ):
                    metrics[name] = metric(None, ema_ev, "unavailable", "missing_indicator")
                side, gap_extent = None, None
            else:
                side = "above" if lo > ema else ("below" if h < ema else "touch")
                metrics["close_ema_relation"] = metric(
                    "above" if c > ema else ("below" if c < ema else "equal"), ema_ev
                )
                metrics["bar_ema_relation"] = metric(side, ema_ev)
                metrics["close_ema_distance"] = metric(c - ema, ema_ev)
                if req["contiguous"] is not True:
                    metrics["ema_gap_count"] = metric(
                        None, ema_ev, "unavailable", "continuity_unverified"
                    )
                    gap_extent = None
                elif side == "touch":
                    gap_count, gap_extent, gap_evidence = 0, "exact", ema_ev
                    metrics["ema_gap_count"] = metric(0, gap_evidence)
                else:
                    if i and previous_side == side:
                        gap_count += 1
                        gap_evidence = join_evidence(gap_evidence, ema_ev)
                    else:
                        gap_count = 1
                        gap_extent = "exact" if previous_side is not None else "lower_bound"
                        gap_evidence = join_evidence(previous_ema_evidence, ema_ev) if i else ema_ev
                    metrics["ema_gap_count"] = metric(gap_count, gap_evidence)
            row["ema_gap_extent"] = gap_extent
            previous_side, previous_ema_evidence = side, ema_ev
        if "atr" in features:
            point = req["atr"]["points"].get(bar["id"])
            atr = point["value"] if point else None
            atr_ev = evidence.indicator(i, point)
            for name, value in (("range_atr", width), ("body_atr", body)):
                if atr is None:
                    metrics[name] = metric(None, atr_ev, "unavailable", "missing_indicator")
                elif atr < 0:
                    metrics[name] = metric(None, atr_ev, "invalid", "negative_atr")
                else:
                    metrics[name] = ratio(value, atr, atr_ev, "zero_scale")
        rows.append(row)
    return rows[-req["output_last"] :] if req["output_last"] is not None else rows


def indicator_rows(req: dict, evidence: Evidence) -> list[dict]:
    bars, period, op = req["bars"], req["period"], req["operation"]
    rows, seed_sum, previous = [], 0.0, None
    # If period exceeds available observations, do not convert it to a float.
    alpha = 2.0 / (period + 1) if op == "ema" and period <= len(bars) else None
    for i, bar in enumerate(bars):
        ev = evidence.span(0, i)
        metrics = {}
        if op == "ema":
            value = bar["close"]
        else:
            value = bar["high"] - bar["low"]
            if i:
                prev_close = bars[i - 1]["close"]
                value = max(value, abs(bar["high"] - prev_close), abs(bar["low"] - prev_close))
            metrics["true_range"] = metric(value, evidence.span(max(0, i - 1), i))
        if i < period:
            seed_sum += value
        if period == 1:
            # Zero smoothing weight removes older dependencies, including their
            # closure/timing metadata. ATR still consumes the previous close.
            local_ev = evidence.span(i if op == "ema" else max(0, i - 1), i)
            metrics[op] = metric(value, local_ev)
        elif i + 1 < period:
            metrics[op] = metric(None, ev, "unavailable", "warmup")
        else:
            if i + 1 == period:
                previous = seed_sum / period
            elif op == "ema":
                previous = alpha * value + (1.0 - alpha) * previous
            else:
                previous = (previous * (period - 1) + value) / period
            metrics[op] = metric(previous, ev)
        rows.append({"id": bar["id"], **metrics})
    return rows


def window(req: dict, evidence: Evidence) -> dict:
    bars = req["bars"]
    ev = evidence.span(0, len(bars) - 1)
    names = (
        "high",
        "low",
        "width",
        "last_close_position",
        "distance_to_high",
        "distance_to_low",
        "net_close_change",
        "overlap_mean",
    )
    data = {
        "metrics": {},
        "high_ids": [],
        "low_ids": [],
        "first_id": bars[0]["id"] if bars else None,
        "last_id": bars[-1]["id"] if bars else None,
        "defined_pair_count": 0,
        "undefined_pair_count": 0,
        "unavailable_pair_count": 0,
        "possible_pair_count": max(0, len(bars) - 1),
    }
    metrics = data["metrics"]
    if not bars:
        metrics.update(
            {name: metric(None, ev, "unavailable", "missing_observations") for name in names}
        )
        return data
    high, low = max(b["high"] for b in bars), min(b["low"] for b in bars)
    data["high_ids"] = [b["id"] for b in bars if b["high"] == high]
    data["low_ids"] = [b["id"] for b in bars if b["low"] == low]
    width, close = high - low, bars[-1]["close"]
    for name, value in (
        ("high", high),
        ("low", low),
        ("width", width),
        ("distance_to_high", high - close),
        ("distance_to_low", close - low),
    ):
        metrics[name] = metric(value, ev)
    metrics["last_close_position"] = ratio(close - low, width, ev, "zero_range")
    metrics["net_close_change"] = metric(
        close - bars[0]["close"], evidence.selected([0, len(bars) - 1])
    )
    ratios = []
    for prev, current in pairwise(bars):
        overlap = max(0.0, min(current["high"], prev["high"]) - max(current["low"], prev["low"]))
        envelope = max(current["high"], prev["high"]) - min(current["low"], prev["low"])
        measured = ratio(overlap, envelope, ev, "zero_envelope")
        if measured["status"] == "ok":
            ratios.append(measured["value"])
        elif measured["status"] == "undefined":
            data["undefined_pair_count"] += 1
        else:
            data["unavailable_pair_count"] += 1
    data["defined_pair_count"] = len(ratios)
    if len(bars) < 2:
        metrics["overlap_mean"] = metric(None, ev, "unavailable", "missing_pairs")
    elif data["unavailable_pair_count"]:
        # Zero envelopes are explicitly excluded; numeric failures are not
        # silently dropped to manufacture an apparently usable mean.
        metrics["overlap_mean"] = metric(None, ev, "unavailable", "numeric_range")
    elif not ratios:
        metrics["overlap_mean"] = metric(None, ev, "undefined", "no_defined_pairs")
    else:
        metrics["overlap_mean"] = metric(sum(ratios) / len(ratios), ev)
    return data


def compare(req: dict, evidence: Evidence) -> dict:
    bars, refs, target_index = req["bars"], req["reference_indexes"], req["target_index"]
    high = max(bars[i]["high"] for i in refs)
    low = min(bars[i]["low"] for i in refs)
    target = bars[target_index]
    ref_ev = evidence.selected(refs)
    combined = evidence.selected([*refs, target_index])
    metrics = {"reference_high": metric(high, ref_ev), "reference_low": metric(low, ref_ev)}
    for name, value in (
        ("high_delta", target["high"] - high),
        ("low_delta", target["low"] - low),
        ("close_delta_high", target["close"] - high),
        ("close_delta_low", target["close"] - low),
        ("high_above_reference", target["high"] > high),
        ("low_below_reference", target["low"] < low),
        ("close_above_reference", target["close"] > high),
        ("close_below_reference", target["close"] < low),
    ):
        metrics[name] = metric(value, combined)
    return {
        "target_id": req["target_id"],
        "reference_ids": req["reference_ids"],
        "metrics": metrics,
    }


def pivots(req: dict, evidence: Evidence) -> list[dict]:
    bars, left, right = req["bars"], req["left"], req["right"]
    rows = []
    for i, bar in enumerate(bars):
        confirmation_id, confirmation_at = None, None
        if req["contiguous"] is not True:
            ev = evidence.span(i, i)
            high = low = metric(None, ev, "unavailable", "continuity_unverified")
            confirmation = "unavailable"
        elif i < left:
            ev = evidence.span(0, i)
            high = low = metric(None, ev, "unavailable", "missing_left_neighbors")
            confirmation = "unavailable"
        else:
            end = min(len(bars) - 1, i + right)
            ev = evidence.span(i - left, end)
            neighbors = [bars[j] for j in range(i - left, end + 1) if j != i]
            high = metric(all(bar["high"] > b["high"] for b in neighbors), ev)
            low = metric(all(bar["low"] < b["low"] for b in neighbors), ev)
            if end < i + right:
                confirmation = "pending_right"
            else:
                confirmation = {
                    "closed": "confirmed",
                    "provisional": "provisional",
                    "unknown": "closure_unknown",
                }[ev["state"]]
                confirmation_id = bars[end]["id"]
                confirmation_at = ev["available_at_ms"]
        rows.append(
            {
                "id": bar["id"],
                "metrics": {"high_so_far": high, "low_so_far": low},
                "confirmation": confirmation,
                "confirmation_id": confirmation_id,
                "confirmation_at_ms": confirmation_at,
            }
        )
    return rows


def point_data(point: dict) -> dict:
    """Echo source fields with the explicitly resolved binary64 price."""
    return {**point["source"], "resolved_price": point["price"]}


def projection(req: dict, evidence: Evidence) -> dict:
    basis, anchor = req["basis"], req["anchor"]
    names = ("low", "high") if basis["type"] == "range" else ("start", "end")
    first, last = (basis[name] for name in names)
    height = abs(last["price"] - first["price"])
    height_ev = evidence.points([first, last])
    target_ev = evidence.points([first, last, anchor])
    sign = 1 if req["direction"] == "up" else -1
    return {
        "basis": {"type": basis["type"], **{name: point_data(basis[name]) for name in names}},
        "anchor": point_data(anchor),
        "metrics": {
            "height": metric(height, height_ev),
            "target": metric(anchor["price"] + sign * height, target_ev),
        },
    }


def risk_reward(req: dict, evidence: Evidence) -> dict:
    entry, stop = req["entry"], req["stop"]
    e, s = entry["price"], stop["price"]
    long = req["direction"] == "long"
    risk = e - s if long else s - e
    risk_ev = evidence.points([entry, stop])
    risk_metric = metric(risk, risk_ev)
    targets = []
    for target in req["targets"]:
        t = target["price"]
        reward = t - e if long else e - t
        reward_ev = evidence.points([entry, target])
        all_ev = evidence.points([entry, stop, target])
        if not math.isfinite(risk):
            rr = metric(None, all_ev, "unavailable", "numeric_range")
        elif risk <= 0:
            rr = metric(None, all_ev, "undefined", "non_positive_risk")
        else:
            rr = ratio(reward, risk, all_ev, "non_positive_risk")
        valid = (e > s and t > e) if long else (s > e and e > t)
        targets.append(
            {
                "point": point_data(target),
                "metrics": {
                    "risk_distance": risk_metric,
                    "reward_distance": metric(reward, reward_ev),
                    "reward_risk": rr,
                    "geometry_valid": metric(valid, all_ev),
                },
            }
        )
    return {"entry": point_data(entry), "stop": point_data(stop), "targets": targets}


def calculate(request: dict) -> dict:
    """Pure one-request operation; admission errors are explicit exceptions."""
    req = admit(request)
    op, bars = req["operation"], req["bars"]
    evidence = Evidence(bars, req["as_of_ms"])
    parameters = {
        "order": "oldest_first",
        "input_order": req["order"],
        "contiguous": req["contiguous"],
        "as_of_ms": req["as_of_ms"],
    }
    limitations = ["binary64_approximation", "measurements_not_trade_permission"]
    if req["contiguous"] is not True and (bars or op not in ("projection", "risk_reward")):
        limitations.append("supplied_observations_continuity_unverified")
    if op == "geometry":
        rows = geometry(req, evidence)
        parameters.update(
            features=req["features"], output_last=req["output_last"], output_count=len(rows)
        )
        for name in ("ema", "atr"):
            if name in req["features"]:
                bundle = req[name]
                parameters[name] = {
                    "source": "supplied",
                    "method": bundle["method"],
                    "period": bundle["period"],
                }
                limitations.append(name + "_upstream_computation_unverified")
                if bundle["method"] is None or bundle["period"] is None:
                    limitations.append(name + "_method_or_period_unknown")
        measurements = [m for row in rows for m in row["metrics"].values()]
        data = {"rows": rows}
    elif op in ("ema", "atr"):
        rows = indicator_rows(req, evidence)
        parameters.update(
            period=req["period"],
            method="sma_seed_ema" if op == "ema" else "wilder",
            seed_rule="first_period_mean" if op == "ema" else "first_observation_range",
        )
        measurements = [m for row in rows for name, m in row.items() if name != "id"]
        data = {"rows": rows}
    elif op == "pivots":
        rows = pivots(req, evidence)
        data = {"rows": rows}
        measurements = [m for row in rows for m in row["metrics"].values()]
        parameters.update(left=req["left"], right=req["right"])
        limitations.append("local_extremum_not_trend_or_support")
        if any(row["confirmation"] == "pending_right" for row in rows):
            limitations.append("right_neighbors_pending")
    elif op == "risk_reward":
        data = risk_reward(req, evidence)
        measurements = [m for target in data["targets"] for m in target["metrics"].values()]
        parameters["direction"] = req["direction"]
        limitations.append("price_geometry_excludes_costs_and_execution_rules")
    else:
        if op == "window":
            data = window(req, evidence)
            limitations.append("window_includes_latest_observation")
        elif op == "compare":
            data = compare(req, evidence)
            limitations.append("strict_price_comparison_not_breakout_confirmation")
        else:
            data = projection(req, evidence)
            parameters["direction"] = req["direction"]
            limitations.append("projection_not_event_validation_or_target_probability")
            if data["metrics"]["height"]["value"] == 0:
                limitations.append("degenerate_projection")
            if req["basis"]["type"] == "move" and req["anchor"]["index"] is None:
                limitations.append("manual_anchor_event_order_unverified")
        measurements = list(data["metrics"].values())
    if any(m["evidence"]["timing"] == "availability_unverified" for m in measurements):
        limitations.append("availability_unverified")
    if any(m["evidence"]["state"] != "closed" for m in measurements):
        limitations.append("provisional_or_unknown_closure")
    ok = sum(m["status"] == "ok" for m in measurements)
    status = "none" if not ok else ("complete" if ok == len(measurements) else "partial")
    return {
        "schema_version": 1,
        "operation": op,
        "status": status,
        "context": req["context"],
        "input_ids": [bar["id"] for bar in bars],
        "parameters": parameters,
        "data": data,
        "limitations": limitations,
    }


class CliParser(argparse.ArgumentParser):
    def error(self, _message):
        reject("invalid_request", "argv", "Expected declared options and explicit byte budgets")


def diagnostic(code: str, path: str, message: str) -> None:
    sys.stderr.write(json.dumps({"code": code, "path": path, "message": message}) + "\n")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = CliParser(description=__doc__, allow_abbrev=False)
        parser.add_argument("--max-input-bytes")
        parser.add_argument("--max-output-bytes")
        args = parser.parse_args(argv)
        budgets = []
        for name in ("max_input_bytes", "max_output_bytes"):
            token = getattr(args, name)
            if token is None or not token.isascii() or not token.isdecimal():
                reject("invalid_budget", "argv", "Byte budgets must be explicit positive integers")
            normalized = token.lstrip("0") or "0"
            maximum = str(sys.maxsize - 1)
            if (
                normalized == "0"
                or len(normalized) > len(maximum)
                or (len(normalized) == len(maximum) and normalized > maximum)
            ):
                reject("invalid_budget", "argv", "Byte budget outside addressable input domain")
            value = int(normalized)
            budgets.append(value)
        raw = sys.stdin.buffer.read(budgets[0] + 1)
        if len(raw) > budgets[0]:
            diagnostic("input_budget_exceeded", "stdin", "Input exceeds caller budget")
            return 3
        result = calculate(parse_request(raw))
        encoded = (
            json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        if len(encoded) > budgets[1]:
            diagnostic("output_budget_exceeded", "stdout", "Output exceeds caller budget")
            return 3
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        return 0
    except RequestError as exc:
        diagnostic(exc.code, exc.path, exc.message)
        return 2
    except (MemoryError, RecursionError):
        diagnostic("resource_exhausted", "$", "Local resources exhausted")
        return 3
    except KeyboardInterrupt:
        diagnostic("interrupted", "$", "Computation interrupted")
        return 130
    except OSError:
        diagnostic("output_io_error", "$", "Local stream I/O failed")
        return 1
    except Exception:
        diagnostic("internal_error", "$", "Unexpected internal failure")
        return 1


if __name__ == "__main__":
    sys.exit(main())
