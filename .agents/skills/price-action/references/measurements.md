# Measurement contract

Read before constructing a calculation request or interpreting its result.
Authority is the bundled `scripts/measure.py` and its offline tests, schema
version 1. Domain interpretations live in the other references; these measurements
are not classifiers, order states, or trade permissions.

## Select the adapter and admit its effects

The script requires an existing Python >=3.11 and only the standard library.
Locate it relative to this Skill. Supply one UTF-8 JSON object without BOM on
stdin, then EOF; consume one JSON response on stdout and diagnostics on stderr.
There is no file/URL input option or JSONL stream.

```text
python -B <resolved-skill-root>/scripts/measure.py --max-input-bytes N --max-output-bytes M
```

N/M are explicit positive integer byte budgets chosen for the actual request and
response, including the response newline. They are host resource bounds, not
trading thresholds. Check `--help` for the local CLI. Do not evade a failed budget
by silently dropping bars, reducing parameters, or truncating JSON.

The script reads stdin and writes stdout/stderr only: no market/model calls,
configuration reads, records, cache, account state, or background service. `-B`
avoids normal bytecode writes, but Python host initialization is not sandboxed by
the script. Use an already admitted runtime; do not run the old app or synchronize
its dependencies. For an existing uv environment, offline/no-project usage is
shown in [README](../README.md); uv is not required by the portable contract.

Without a compatible runtime or execution authority, use supplied measurements,
explicit manual arithmetic, or an honest unavailable calculation. Do not claim
executed output. No other installed Skill or the old repository is a runtime
dependency.

## Shared request fields

Allowed fields are the shared fields below plus only the selected operation's
fields. No aliases, additional object fields, duplicate JSON keys, inferred
order/direction, or repair of inconsistent observations are accepted.

| Field | Meaning |
| --- | --- |
| `schema_version` | Required integer `1`, not a string or boolean. |
| `operation` | Required supported operation name from the table below. |
| `bars` | Required array for observation operations; optional for manual-only projection/RR. May be empty where no referenced ID is required. |
| `order` | Required `oldest_first` or `newest_first` whenever bars are supplied, including an empty array. A scalar request without bars may omit it. If supplied alone, it must still be valid. |
| `contiguous` | Optional boolean/null declaration. Omitted/null is unknown, not true. The script does not verify the caller's declaration against a market calendar. |
| `as_of_ms` | Optional integer/null observation cutoff, UTC milliseconds. |
| `context` | Optional ordinary JSON object, echoed but not used to select arithmetic or verify market/product facts. |

Each bar admits only `id`, `open`, `high`, `low`, `close`, `closed`, `time_ms`,
and `available_at_ms`. ID is a unique nonblank string. Prices must be finite
numbers, not strings/booleans; supplied H/L must be ordered and any supplied O/C
must be inside the supplied bounds. Only prices required by the operation need
be present. All supplied bars are validated, even those not consumed by a sparse
reference selection.

`closed=true/false/null` means closed/forming/unknown; omission is unknown.
`time_ms` is bar-open time; `available_at_ms` is availability of the supplied
version, not an inferred bar close. Both are integer/null if supplied. Known open
times must strictly increase after the declared order is normalized. Results are
oldest-first; input identities are retained, not replaced with positional labels.

With a cutoff, any supplied bar, indicator point, or manual Point whose declared
availability exceeds it rejects the request. The script does not trim future
bars. Missing availability is allowed but cannot establish historical validity.
Closed bars without version-availability metadata do not prove that revised data
was knowable at an earlier decision time.

## Choose the operation

| Operation | Prices and extra fields | Output location and meaning |
| --- | --- | --- |
| `geometry` | OHLC; optional `features`, `output_last`, `ema`, `atr`. | `data.rows[].metrics`: selected single/adjacent/indicator relationships. |
| `ema` | Close; required positive integer `period`. | `data.rows[].ema`: SMA seed, then EMA of supplied closes. |
| `atr` | HLC; required positive integer `period`. | `data.rows[].true_range` and `.atr`: first-observation range, mean seed, then Wilder smoothing. |
| `window` | HLC; no extra fields. | `data.metrics`: envelope and relationships for all supplied bars, including the latest. |
| `compare` | HLC; required `target_id`, nonempty unique `reference_ids`. | `data.metrics`: selected prior-reference envelope and target differences/crossings. |
| `pivots` | HLC; required positive integer `left`, `right`; meaningful relations need `contiguous=true`. | `data.rows[]`: strict local-extremum measurements plus comparison-window phase. |
| `projection` | Required `basis`, `anchor`, `direction=up/down`; referenced prices must be supplied. | `data.metrics.height/target` and source echoes; pure equal-distance geometry. |
| `risk_reward` | Required `direction=long/short`, `entry`, `stop`, nonempty `targets`; referenced prices must be supplied. | `data.targets[].metrics`: signed distances, ratio, and price orientation. |

### Geometry and supplied indicators

`features` is a nonempty unique subset of `candle/relations/ema/atr`, defaulting
to `["candle","relations"]`. `output_last` is an optional positive integer,
limiting output rows without deleting historical calculation context. It is not
supported on the other operations.

- Candle metrics: `range`, `body`, `upper_wick`, `lower_wick`, `direction`,
  `body_ratio`, `upper_wick_ratio`, `lower_wick_ratio`, and `close_position`.
- Relations: `inside_prev_observed`, `outside_prev_observed`, `equal_range`,
  `overlap_envelope_ratio`, `high_delta_prev`, `low_delta_prev`, `ii/iii/ioi`.
  Pair relations describe supplied neighboring observations even when continuity
  is unknown; sequential `ii/iii/ioi` require declared continuity and neighbors.
  Inclusive inside/outside relations can both be true for equal envelopes.
- EMA metrics: `close_ema_relation`, `bar_ema_relation`, `close_ema_distance`,
  `ema_gap_count`; each row also has `ema_gap_extent=exact/lower_bound/null`.
  Count is same-side whole-bar separation, not a universal "20GB" permission.
- ATR metrics: `range_atr`, `body_atr`. Missing, zero, and negative supplied ATR
  produce respectively unavailable, undefined normalization, and invalid metrics.

An indicator bundle admits `method` (nonblank string/null), `period` (positive
integer/null), and `points` (array). Each point admits `bar_id`, required
`value` (finite number/null), optional `available_at_ms` (integer/null). IDs must
be supplied and unique within that bundle. Supply a bundle only when its feature
is selected. Missing/omitted points are missing indicators, not zero or a request
to compute one. Upstream method/period declarations are echoed, not authenticated.

```json
{"schema_version":1,"operation":"geometry","features":["ema"],"order":"oldest_first","contiguous":true,"bars":[{"id":"e1","open":11,"high":13,"low":11,"close":12,"closed":true}],"ema":{"method":"supplied_example","period":2,"points":[{"bar_id":"e1","value":10}]}}
```

Expected: whole-bar `above`, gap count 1, `ema_gap_extent="lower_bound"` because
earlier history is absent. Availability is unverified; the method label does not
establish how the upstream EMA was computed.

### Computed EMA/ATR

EMA's first `period-1` values are unavailable/warmup. The first `period` closes
seed their arithmetic mean; thereafter alpha=2/(period+1) and
EMA=alpha*C+(1-alpha)*previous EMA. ATR starts TR with H-L, then
TR=max(H-L, |H-previous C|, |L-previous C|). Its first `period` TR values seed
their mean; thereafter ATR=(previous ATR*(period-1)+TR)/period.

These are calculations on supplied observations. No history is fetched and no
market-calendar continuity is inferred. Warmup is not a global sample rejection.
Period 1 removes older smoothing dependencies; ATR still uses the preceding
provided close where one exists. `parameters` reports method, seed, and period.

```json
{"schema_version":1,"operation":"ema","order":"oldest_first","period":2,"bars":[{"id":"s1","close":10},{"id":"s2","close":12},{"id":"s3","close":14}]}
```

Expected: unavailable/warmup, then 11, then approximately 13. Continuity and
closure are unknown; these are not certified market-period indicators.

### Window and strictly prior comparison

Window returns `high/low/width`, `last_close_position`, `distance_to_high/low`,
`net_close_change`, and `overlap_mean`. `high_ids/low_ids` preserve all ties.
Mean overlap uses exactly N-1 internal pairs, each intersection/envelope ratio.
`defined_pair_count`, `undefined_pair_count`, `unavailable_pair_count`, and
`possible_pair_count` expose the sample. Zero-envelope pairs are excluded with
counts; a numeric-range failure makes the mean unavailable, not a quietly reduced
sample. Net close change uses only endpoints and is neither trend nor drawdown.

Compare forms `reference_high/low` from only the selected IDs, all strictly before
the target. Signed `high_delta`, `low_delta`, `close_delta_high/low` and strict
`high_above_reference`, `low_below_reference`, `close_above_reference`,
`close_below_reference` are independent. Equality is not a crossing; later and
intervening unselected bars do not expand the reference or its provenance.

```json
{"schema_version":1,"operation":"compare","order":"oldest_first","target_id":"t","reference_ids":["r"],"bars":[{"id":"r","high":12,"low":8,"close":10,"closed":true},{"id":"t","high":13,"low":9,"close":11,"closed":true}]}
```

Expected: `high_above_reference=true` but `close_above_reference=false`. This is
an excursion beyond the selected high, not confirmed breakout continuation.

### Pivots and confirmation timing

Strict high/low tests compare each center with all `left` older and up to `right`
visible newer neighbors. Equal prices do not satisfy a strict extremum. High/low
can both be true. Without continuity or sufficient left neighbors, the relations
are unavailable. The row's `confirmation` is the window's evidence phase:

- `pending_right`: insufficient right neighbors, even if a relation is true so far;
- `provisional`: full window includes a forming observation;
- `closure_unknown`: full window has unknown closure and no forming observation;
- `confirmed`: full window is closed; this does not say the center is an extremum;
- `unavailable`: continuity or left-neighbor precondition is missing.

Only `confirmed` **and** the corresponding `high_so_far/low_so_far.value=true`
establish a confirmed local extremum. `confirmation_id` is the last required
right neighbor when a full admitted window exists. `confirmation_at_ms` is the
maximum declared availability of inspected evidence, or null; outside the
confirmed phase it is not a completed-extremum confirmation time. An earlier
cutoff must never borrow that later information.

```json
{"schema_version":1,"operation":"pivots","order":"oldest_first","contiguous":true,"left":1,"right":1,"as_of_ms":2,"bars":[{"id":"p0","high":10,"low":7,"close":9,"closed":true,"available_at_ms":1},{"id":"p1","high":12,"low":8,"close":11,"closed":true,"available_at_ms":2}]}
```

Expected for p1: `high_so_far=true`, `confirmation="pending_right"`, and null
confirmation ID/time. It is not a confirmed pivot despite root `status="partial"`.

### Explicit Points, projection, and gross RR

A Point is either `{"bar_id":"id","field":"open|high|low|close"}` referencing
an actually supplied field, or `{"price":number,"label":"nonblank source"}`
with optional `available_at_ms`. Do not mix source forms. Outputs echo source
fields with `resolved_price`; that field is output-only. A manual label cannot
verify structure, timing, or event order. Manual sources retain unknown closure.

Projection basis is `{type:range,low:Point,high:Point}` with high>=low, or
`{type:move,start:referencePoint,end:referencePoint}` with chronological start<end,
nonzero price movement matching direction, and any referenced anchor no earlier
than end. Height is absolute endpoint distance; target is anchor plus/minus
height. A manual move anchor leaves event order unverified. Zero range height is
valid but flagged `degenerate_projection`; no leg/event/hit probability is proven.

```json
{"schema_version":1,"operation":"projection","direction":"up","basis":{"type":"range","low":{"price":90,"label":"given lower level"},"high":{"price":100,"label":"given upper level"}},"anchor":{"price":100,"label":"given anchor"}}
```

Expected: height 10 and target 110, with unknown closure/availability. This is not
proof of an existing range or approved profit target.

For long RR, risk=entry-stop and reward=target-entry; for short, the signs reverse.
Each explicit target is independent. Ratio requires positive finite risk;
nonpositive risk is undefined, negative reward retains its sign, and overflow
is unavailable/numeric_range. `geometry_valid` only measures the directional
three-price ordering and can be false with root status complete. No costs, quote
grid, fills, sizing, order availability, win rates, or stop/target rewrites exist.
The [README example](../README.md) demonstrates a supplied-price RR calculation.

## Consume the result, not just the exit code

The response has `schema_version`, `operation`, root `status`, echoed `context`,
chronological `input_ids`, `parameters`, `data`, and `limitations`.
Each measurement is `{value,status,reason,evidence}`:

- `ok`: value exists, including real zero or false;
- `unavailable`: missing context/warmup/continuity or a numeric-range failure;
- `undefined`: e.g. a zero denominator;
- `invalid`: e.g. negative supplied ATR.

Non-ok values are null, not imputed zero/false. Root `complete/partial/none`
summarizes availability of selected output metrics, not confirmation or accuracy.
Evidence includes `first_id/last_id/count`, `state=closed/provisional/unknown`,
`available_at_ms`, and `timing=checked_declared_availability/availability_unverified`.
Discrete references count unique consumed bar IDs, not every intervening bar;
manual Points count no bar IDs. Timing checks validate declarations, not feed
truth, absence of revisions, or actual market access.

Binary64 finite approximations are used, with no intermediate tick rounding or
tolerance. Nonfinite derived metrics become unavailable/numeric_range; no
NaN/Infinity is emitted. Finite input overflow and nonzero JSON literal underflow
are rejected; quoted numeric strings cannot evade this boundary.

| Exit | Meaning and response |
| --- | --- |
| 0 | Help or complete JSON response; metric/root availability can still be partial/none. |
| 2 | Admission failure: invalid JSON/request/bar/reference/budget, unsupported version/operation, or future evidence. Empty stdout, stderr JSON diagnostic. |
| 3 | Input/output byte budget exceeded or local resources exhausted. No intentionally truncated response. |
| 1 | Internal failure or stream I/O failure. |
| 130 | Caught interruption. External termination may have different host-observed status. |

Check successful exit **and** a complete parseable response for a calculation.
Diagnostics are `{code,path,message}` on stderr without dumping source values.
An external kill or output I/O failure can leave partial transport output; do not
relabel it a complete response. No automatic retry or persistent business state
needs recovery. Report the affected unavailable measurement and retain compatible
explanation instead of pretending the requested operation succeeded.
