# Contributing to Technical Trading Skill

This fork focuses on the portable [price-action bundle](skills/price-action/README.md).
Issues and pull requests should describe the intended result, affected contract,
and evidence supporting the change.

## Scope and ownership

- `skills/price-action/SKILL.md` owns capability scope and reasoning behavior.
- `references/` inside the bundle owns focused interpretation guidance and the
  measurement contract; avoid duplicating these rules in the entry or root docs.
- `scripts/measure.py` owns stateless, standard-library arithmetic on explicit
  inputs. Preserve input admission, cutoff/closure semantics, missingness,
  provenance, output budgets, and unchanged caller-supplied prices.
- Bundle `tests/` owns offline calculation, CLI, and portability checks.

Do not introduce old data-layer dependencies, credentials, acquisition, account
state, orders, fixed trading gates, or hidden repricing into the bundle.
Changes to trading definitions or empirical claims need their own research
evidence; passing software tests does not establish their market value.

This repository contains a Skill bundle, not a desktop application or an
installable Python package. The measurement adapter needs Python's standard
library only; no API keys, GUI, or project dependency synchronization are required.
Legacy code is available in Git history, not a second development target in the
current tree.

## Offline checks

Use an existing Python >=3.11 and `uv`. From the repository root in PowerShell:

```powershell
uv run --no-project --offline --no-python-downloads --no-cache --python 3.11 python -B -m unittest discover -s skills/price-action/tests -p 'test_*.py'
```

The tests use only the standard library and create/clean their own temporary
directories under the bundle's `tests/`. If a sandbox denies access to those
fixtures, report the blocked check and obtain permission for that bounded effect;
do not label it a pass. Repeat on another supported Python version when changing
runtime-sensitive behavior.

With an existing Ruff executable, check the bundle's Python files without
creating a cache. The root `ruff.toml` preserves the bundle's Python 3.11 target,
100-column formatting, and selected lint rules:

```powershell
ruff check --no-cache skills/price-action/scripts skills/price-action/tests
ruff format --check --no-cache skills/price-action/scripts skills/price-action/tests
```

For documentation changes, verify relative links and runnable examples. Keep all
Skill-facing instructions and documentation in English. State whether evidence
comes from arithmetic/CLI tests, static instruction review, observed model
behavior, or market research; do not substitute one for another. Fresh-context
model tests are not a required contribution gate.

## Before committing

- Keep a change focused and explain compatibility or observable behavior changes.
- Preserve provenance and the original AGPL-3.0-or-later declaration.
- Inspect the staged diff, not just the working directory. Stage intended paths
  explicitly; local authoring plans under `.agents/plan/` are not public docs.
- Do not publish API keys, `.env` files, private keys, local settings, logs,
  analysis records, account data, or private market evidence.
- Keep new regression fixtures synthetic or clearly authorized for publication.

For bug reports, provide a minimal sanitized input, operation, Python version,
expected result, actual output/status, and reproduction command. For instruction
issues, include the relevant premise and boundary that failed without disclosing
private trading records.
