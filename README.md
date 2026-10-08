# Technical Trading Skill

A portable, English price-action Skill for interpreting supplied market evidence,
developing conditional opening ideas for **human confirmation**, and reviewing
explicitly supplied plans. This fork extracts selected knowledge and independent
measurements from PA_Agent; it is not a new data service or an automated trader.

## Start here

Clone this fork using Git (network access required):

```powershell
git clone https://github.com/nostalume/Technical-Trading-Skill.git
cd Technical-Trading-Skill
```

Read the [bundle guide](skills/price-action/README.md) for usage, a runnable
measurement example, verification commands, and provenance. The
[Skill entry](skills/price-action/SKILL.md) is the instruction entry point;
the [measurement contract](skills/price-action/references/measurements.md)
defines the optional calculation interface.

The handoff unit is the complete `skills/price-action/` directory. Keep its
instructions, references, script, tests, guide, and license together. Copying it
does not install or register it with an agent host; use your host's own discovery
configuration. No old application dependencies or API credentials are needed for
the bundled measurements.

For a user-level copy, copy the complete bundle to
`$HOME/.agents/skills/price-action/` **without moving the repository source**.
Do not overwrite an existing installed copy without reviewing its local changes.
The bundle guide's commands run from the bundle directory, so they work for either
copy. This repository does not need a second bundle under its own `.agents/`.

## What it provides

- Candle geometry, repeated tests, trend/range context, breakout/retest sequences,
  and conditional reversal-structure interpretations.
- Source-bound candidate plans: premises, triggers, entry/invalidation/stop/target
  rationale, competing scenarios, and waiting conditions.
- A bounded reasoning loop that revises affected claims from supplied evidence,
  rather than polling markets or maintaining account/position state.
- Eight standalone calculations: `geometry`, `ema`, `atr`, `window`, `compare`,
  `pivots`, `projection`, and `risk_reward`.

Supply evidence from your own data project. Crypto and A-share short-term analysis
are intended use cases, not verified product integrations. The caller supplies
product/venue, timeframe, observation cutoff, permitted direction, and holding
horizon when they matter; the Skill does not impose a universal trading schedule.
Acquisition, product-specific rules, risk policy, and execution remain outside
the bundle.

The extraction does not retain the old application's fixed trade-permission
thresholds, guessed ticks, hidden stop widening, or automatic price changes to
satisfy a reward/risk gate. Measurements do not automatically classify complex
patterns or authorize trades.

## Verification and limits

With an existing `uv` executable and Python 3.11+, run from the repository root:

```powershell
uv run --no-project --offline --no-python-downloads --no-cache --python 3.11 python -B -m unittest discover -s skills/price-action/tests -p 'test_*.py'
```

The suite uses only the standard library. It creates and removes its own temporary
fixtures under the bundle's `tests/` directory; the host must permit that test
effect. The flags run without project dependency resolution and prevent downloads.
No project synchronization is needed to consume this Skill.

Offline calculation, CLI, and detached-bundle checks have passed on Python 3.11
and 3.14. Instruction boundaries and the reasoning loop have been reviewed
statically. These checks do **not** establish model behavior, host discovery,
live-market suitability, or profitability. This is an exploratory decision aid,
not a production-validated trading system. It never places orders; trading
decisions remain with the user.

## Repository scope and source history

The current tree contains the standalone Skill and its repository documentation,
licenses, and development settings. The legacy desktop application, data adapters,
model connectors, prompts, application tests, dependency manifest/lockfile,
launchers, deployment guides, feedback screenshots, and sponsorship assets have
been removed. There is no desktop application or Python package to install here.

Historical source paths in the bundle's provenance notes refer to PA_Agent revision
`cd0aca2da684fb342bc25f6e14bc980dc8480dab`, not current runtime dependencies.
The original code and documentation remain available in Git history; see
[the extraction source revision](https://github.com/nostalume/Technical-Trading-Skill/tree/cd0aca2da684fb342bc25f6e14bc980dc8480dab).

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for the Skill development scope and checks.
The bundle guide records source provenance and deliberately excluded behavior.
The original **AGPL-3.0-or-later** declaration is retained; see [LICENSE](LICENSE)
and the [bundle license](skills/price-action/LICENSE).
