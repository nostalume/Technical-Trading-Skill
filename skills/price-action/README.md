# Price-action Skill: analysis, candidate plans, and measurements

The English [Skill entry](SKILL.md) analyzes supplied price evidence, develops
conditional opening ideas for human review, and reviews/updates supplied plans.
It selects focused references for candles/repeated tests, context/events,
reversal structures, and [candidate planning](references/candidate-plans.md).
Standalone calculations measure explicit
inputs; they do not automatically recognize complex patterns or grant permission
to trade. Available operations are `geometry`, `ema`, `atr`, `window`, `compare`,
`pivots`, `projection`, and `risk_reward`.

Offline arithmetic, CLI, and detached-bundle checks have passed on Python 3.11
and 3.14. Instruction boundaries and the bounded reasoning loop were reviewed
statically; **model behavior and runtime discovery remain
unverified**. This is not a production-validated trading system or a profitability
claim. No global installation, model integration, data adapter, account management,
or automatic order execution is included.

## Consume or move the bundle

The handoff unit is the complete `skills/price-action/` directory. Keep its
`SKILL.md`, `references/`, `scripts/`, `tests/`, `README.md`, and `LICENSE`
together so relative links and verification resources remain valid. Repository
development settings and local authoring plans are not needed. This handoff does
not install or register the Skill with a host; discovery configuration remains
the host's responsibility.

Supply evidence from your existing data project; no old data-layer interface or
new acquisition service is required. The caller owns source integrity, product/
price basis, version availability, applicable market rules, and any later
execution. Use the measurement JSON contract only when choosing that calculation
adapter, not as a compulsory input format for every qualitative analysis.

For subsequent reviews, explicitly supply the prior plan and comparable new
evidence. The Skill checks the affected premises and stops with a bounded answer;
it does not retain plan history, watch for new bars, or manage a position. Building
new signal definitions or validating their empirical value is separate research,
not an implicit extension of a case interpretation.

Automatic H/L counting, regime/spike/Always In classification, and complex-pattern
recognition are not implemented. The references support conditional explanations;
raw measurements do not become classifier outputs. External data adaptation,
host integration, and live execution remain outside this bundle, rather than
hidden prerequisites for reading or running it.

## Request an analysis or conditional idea

Provide the evidence you already have and the result you want: explanation,
measurement, candidate idea, or review/update of an explicitly supplied plan.
Only include context that can change the result, such as product/venue, timeframe,
observation cutoff, permitted direction and holding horizon. For example:

> Explain the supplied range boundary first. If the evidence supports a long
> candidate, describe its trigger, source-bound entry/stop/target rationale and
> waiting conditions. My intended horizon is intraday to at most one week. I will
> confirm manually; do not fetch data, place orders or invent missing prices.

This example does not supply any market evidence; by itself it cannot yield exact
prices. A supported answer can be a watch condition or an incomplete candidate,
not necessarily a trade. See the entry's routes instead of loading every reference.
Model adherence to this request has not been tested here.

## Run one measurement

For this example, use an existing `uv` executable and Python >=3.11. The portable
script itself requires Python only. No application dependencies, configuration,
credentials, or market connection are required. In PowerShell 7, run from the
bundle directory containing `SKILL.md`: `skills/price-action/` in the repository,
or `$HOME/.agents/skills/price-action/` for a user-level copy. The commands below
use paths relative to that bundle, not to the repository root:

```powershell
$payload = @'
{"schema_version":1,"operation":"geometry","features":["candle"],"order":"oldest_first","as_of_ms":20,"bars":[{"id":"a","open":10,"high":14,"low":8,"close":12,"closed":true,"available_at_ms":20}]}
'@
$payload | uv run --no-project --offline --no-python-downloads --no-cache --python 3.11 python -B scripts/measure.py --max-input-bytes 10000 --max-output-bytes 100000
```

Expect `status="complete"`, `data.rows[0].metrics.range.value=6`, and
`body_ratio.value` approximately `1/3`. "Complete" means the selected
measurements are available, **not** that a trade is authorized or profitable.

The calculation reads stdin and writes JSON to stdout; it does not fetch data or
save analysis. Budgets are explicit UTF-8 byte limits, including the response's
final newline, not minimum bar counts. `--no-project` skips project discovery;
`--offline --no-python-downloads` prevent downloads. Do not run `uv sync`.
If PATH selects a broken tool-manager proxy, invoke your existing `uv.exe` by
absolute path instead of modifying global settings.

The script can be moved independently. It does not import `pa_agent` or read
configuration, prompts, or records from the current directory. The caller still
owns Python host configuration; this script is not a runtime sandbox.

## Choose a calculation

Read the [measurement contract](references/measurements.md) for accepted fields,
formulas, source Points, confirmation/provenance semantics, result locations, and
failure handling. It is the canonical interface reference for the bundled script.
The [Skill entry](SKILL.md) routes interpretation to the relevant knowledge;
there is no need to read all references or execute all calculations for one question.

## Recalculate a supplied plan without changing prices

Send this JSON to the same CLI:

```json
{"schema_version":1,"operation":"risk_reward","direction":"long","entry":{"price":100,"label":"given entry"},"stop":{"price":98,"label":"given stop"},"targets":[{"price":106,"label":"given target"}]}
```

Expect risk_distance=2, reward_distance=6, reward_risk=3, with stop still 98.
This is arithmetic on supplied prices, not evidence that a structural invalidation
level is appropriate, shorting is permitted, net profitability is positive, or an
order is currently executable.

## Offline verification

```powershell
uv run --no-project --offline --no-python-downloads --no-cache --python 3.11 python -B -m unittest discover -s tests -p 'test_*.py'
```

Tests use only the standard library. Isolation tests create and clean up their own
temporary directories under `tests/`. A host sandbox denying access to newly
created private directories must explicitly permit this controlled test effect;
do not report a blocked test as passing. These tests do not validate live markets,
model behavior, or profitability.

## Provenance and license

Source material comes from PA_Agent revision
`cd0aca2da684fb342bc25f6e14bc980dc8480dab`. The paths below identify historical
sources in Git history, not files required in the current tree. The legacy
application and its supporting material have been removed from this tree:

- `pa_agent/ai/kline_features.py`: candle, inside/outside, overlap, and EMA
  relationships; admission, missingness, timing, and independent inputs rewritten.
- `pa_agent/indicators/ema.py`, `atr.py`: mean seeds, EMA and Wilder smoothing;
  no incremental persistence or data-layer dependencies.
- `pa_agent/ai/market_features.py`, `structure_levels.py`: window, local-extremum,
  and projection material; prior references, strict neighborhoods, confirmation
  timing, and explicit anchors rewritten, not automatic trend/leg/breakout labels.
- `pa_agent/util/trade_metrics.py`: signed risk/reward distances; explicit
  direction replaces inference, and RR gates/stop widening are not retained.

Knowledge references are rewritten from the same revision's `prompt_engineering/`
material: market diagnosis, bar-by-bar analysis, bull/bear channels and spikes,
ranges, second attempts and bar signals, H/L counting, breakout tests/failures,
EMA terminology, overlap, retest candidates, wedges, final flags, major reversals,
triangles, double structures, and measured moves. Numbered source topics are
identified at the end of each reference. The original glossary supplies term
expansions, not mandatory enums or routing. The old binary decision tree, risk/
order protocol, local external-knowledge paths, and source instructions are not
runtime dependencies. Planning also draws from stop/target and continuity
questions, rewritten without account state, default timers or hidden repricing.

These files preserve selected concepts, not evidence that the source's empirical
claims are true or that every source sentence was migrated. Original-author
attributions have not been independently authenticated. Unsupported probabilities,
universal direction/shape bans, hidden stop changes, and cross-product tick/session
templates are excluded rather than disguised as configuration.

Old classification thresholds, trade permissions, stop widening, and guessed
ticks are excluded. The original **AGPL-3.0-or-later** declaration is retained;
see [LICENSE](LICENSE). This preserves provenance and licensing rather than
granting a new license, making a legal determination, or authorizing publication.
