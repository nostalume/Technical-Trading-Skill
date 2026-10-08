# Candidate plans and evidence updates

Read when the user requests an opening idea, a conditional trade plan, or an
update/review of a supplied plan. For a request only to explain a chart or pattern,
complete that explanation without manufacturing a plan. This reference owns
planning relations, not order execution, account state, or empirical validation.

## From a hypothesis to a candidate

Start with the structure and material alternative supported by the supplied
evidence. Express the action as a conditional proposition, not an unconditional
prediction: what observation would support considering which direction, what
would contradict it, and what currently prevents the idea from being ready for
human consideration? A countertrend or range-boundary idea is not intrinsically
forbidden; assess its premises and the user's actual permitted strategy scope.

Do not require a complete intake form before explaining compatible evidence.
Resolve only missing choices/facts that can change the proposed action. Product,
venue, instrument type, timeframe, price basis, cutoff, allowed direction and
holding horizon matter when they change which plan the prices can support.
Missing a price source prevents that precise price, not all structural analysis.

For a useful candidate, make the following relations inspectable where relevant;
they are not a compulsory report schema or a fixed sequence of model calls:

| Relation | Question the answer must resolve |
| --- | --- |
| Premise and alternative | Why would this action follow from the observed structure, and what competing reading could change it? |
| Trigger | Which event, at which referenced level/structure, would support considering the action? Is it observed, provisional, or still pending? |
| Entry proposition | Is this a proposed price/zone, a future price condition, or a current quote? What is its source and what has not been verified? |
| Invalidation and protection | What would contradict the premise? If a protective stop is proposed, why that price/condition and what does it actually protect? |
| Target rationale | Which supplied structure, explicit projection, or user-selected rule supports each objective? What nearer competing structure matters? |
| Waiting / withdrawal / review | What is missing, what would change the idea, and which user-imposed constraint would exclude it? |

State a useful bounded outcome: conditional candidate, incomplete price plan,
observation pending, premise contradicted, unverifiable update, or outside the
user's stated constraints. These descriptions need not become an enum or binary
trade gate. If evidence does not favor a directional candidate, say why and which
observation would distinguish the alternatives; don't supply opposed orders to
avoid choosing or manufacture confidence to avoid waiting.

## Trigger, entry and stop are different propositions

A trigger needs an observable event: a strict price crossing, a closed-bar result,
a sourced boundary test with a specified response, or another explicit user
condition. Name its reference and whether it requires closure. A wick excursion,
forming close, closed-bar break, and later retest are not interchangeable.
Do not invent follow-through at the latest bar or count future pivot confirmation
as evidence that the earlier setup was ready.

An event condition is not its execution price. "Close above 100" does not imply
an entry fill at 100. A proposed limit price is not a current executable quote;
a projected next-bar price is not supplied evidence. If the entry will depend on
a future observation, leave it conditional rather than fabricate a precise fill.
For a proposed zone, give sourced bounds and the selection rationale; do not
silently introduce a tolerance around a single price.

Every numerical level must come from a supplied price/Point, an identified bar or
structure, or a reproducible calculation with declared endpoints/parameters.
Distinguish user-supplied plan prices, observed levels, and newly proposed derived
levels. A label such as "support" is a hypothesis to explain, not proof of its
effectiveness. Use the measurement contract when calculating, or show explicitly
labeled manual arithmetic if execution is unavailable.

Separate **structural invalidation** from a **protective stop**:

- Invalidation states which observation contradicts the hypothesis, e.g. a
  closed return through a selected boundary. Specify strict/inclusive comparison,
  observation timeframe and closure requirement when the distinction matters.
- A stop proposal expresses price/risk protection, not proof that the hypothesis
  is false at every intrabar excursion. Explain any difference from the structural
  condition. A close-based review condition is not a guaranteed intrabar risk cap.
- If a tick/buffer/order condition is needed, use a supplied or verified product
  rule and explicitly chosen buffer policy. Do not infer tick size from decimal
  places or import "one tick", ATR multiples, or bar-height limits as defaults.
- Evaluate orientation and distance without rewriting supplied prices. A stop at
  entry gives nonpositive risk in gross RR; a stop on the wrong side is not fixed
  silently. Describe the inconsistency and any separately labeled alternative.

Do not move a stop, entry, or target just to meet a numerical preference. If the
user requests alternatives, each must have its own structural/policy rationale
and remain distinguishable from the original. There is no order submission,
stop replacement, position management, or inferred account affordability here.

## Targets and ratios do not create an edge

Describe the candidate objective's source and distance: an opposing boundary,
previous extreme, identified retest level, explicit measured move, or a
user-selected R multiple. Discuss nearer conflicting structure rather than
selecting a farther projection solely to improve the reported RR. Source-defined
"magnet" or "measured move" language does not establish hit probability.

A measured move needs selected endpoints, their order, direction and anchor.
Explain why that geometry is relevant to the hypothesis; the script cannot
validate a completed leg or choose an appropriate target for the analyst. Keep
target contact, price penetration, and any later response distinct. There is no
compulsory TP1/TP2 pair, fixed target priority or automatic partial-exit schedule.

Calculate gross distances/RR only for prices whose meaning is clear. Different
targets can describe different scenarios; do not average their ratios or treat
the most distant ratio as proof of the nearer objective. If a user requests
fixed-R targets, label them policy-derived rather than observed structural levels.

A supplied minimum RR or risk constraint is a user policy for that request, not
a market law. Report whether the unchanged candidate meets it; if not, wait or
discuss separately justified alternatives within the user's scope. Without such
a policy, do not install an implicit RR >= 1, confidence cutoff, vote requirement,
or estimated-win-rate equation. The absence of a gate is not a reason to recommend
every geometrically valid setup.

Fees, spread, slippage, funding/borrow terms and price-grid/order rules can change
the practical proposition. Use applicable supplied/verified evidence if making a
claim that depends on them. Otherwise label the plan as structural/conditional,
RR as gross geometry, and net viability/executability as unverified. Do not invent
cost estimates, profit probabilities or positive expectancy to make a plan look
complete. Missing those facts need not block a conditional structural discussion.

### Arithmetic-only illustration

The following synthetic user-supplied price plan straddles the old 1R threshold.
It illustrates unchanged-price arithmetic, not a strategy or recommendation:

```json
{"schema_version":1,"operation":"risk_reward","direction":"long","entry":{"price":100,"label":"supplied entry"},"stop":{"price":98,"label":"supplied stop"},"targets":[{"price":101.8,"label":"supplied nearby target"},{"price":102.2,"label":"supplied alternative target"}]}
```

Expected: risk 2, gross rewards approximately 1.8 and 2.2, ratios approximately
0.9 and 1.1, with stop still 98. Both orientation metrics are true; neither target
automatically grants permission to trade. If the current user requires RR >= 1,
only the second meets that arithmetic policy; its structural plausibility, costs
and suitability still need their own evidence. The example is not a standing rule
to select the farther target, and binary64 values are approximate.

## Holding horizon and product applicability

Apply the horizon the current user states. Intraday through a maximum of one week
is a possible request constraint, not a default for unrelated analyses. Distinguish
evidence cutoff, entry-opportunity lifetime and intended holding horizon. A day
bar is not a promise of a same-day exit; a projection has no time-to-target estimate
unless supported by separate evidence. If a proposed idea depends on a longer
horizon, expose that mismatch instead of stretching the user's limit.

Use a user-selected deadline, session condition or meaningful structural event
when defining expiration/reassessment. Do not invent an automatic three-bar
expiry, flip cooldown, daily holding requirement or target-arrival forecast. If
an exact deadline matters, establish its timezone/calendar and what starts the
clock. An expired analytical proposal does not mean a resting order was cancelled.

Market labels are not product capabilities. An equity-related instrument offered
on a crypto venue may have a different underlying/price basis from the equity;
a cash product and derivative sharing a ticker are not interchangeable evidence.
For A-shares, crypto, or any other market, establish the actual product identity
and applicable permissions/rules before calling an action feasible. Do not embed
unverified jurisdiction/venue/session/shorting/settlement rules in this Skill.

A bearish scenario can justify avoiding a long idea or observing a level without
implying a new short position. Ask whether short exposure is permitted only when
it changes the requested action. Current-rule lookup or live quote retrieval
belongs to a separately authorized source owner; when unavailable, identify the
exact affected execution claim and retain compatible analysis. No implicit
network connection or external data-layer integration is introduced.

## Update only the prior plan actually supplied

Use a prior plan only when explicitly provided in this request's admitted context.
Do not search CSV files, load the last symbol/timeframe record, or infer a past
position. Preserve the prior proposal and its observation cutoff while comparing
new evidence; a change in opinion does not change historical prices or make later
confirmation available earlier.

Establish comparability before saying the same plan persists or is invalidated:
product/venue/instrument, price basis/adjustments, timeframe, direction, structural
anchors, trigger/invalidation definition, horizon and source identities where
they affect that claim. The same ticker or a nearby entry price is insufficient.
Use stable source IDs, not renumbered window positions. An explicitly compatible
mapping can support comparison; an unknown or mismatched basis leaves the update
unverifiable while permitting a separate fresh analysis.

Describe the delta at its smallest premise:

- Which newly supplied observation is actually later/changed, and was it available
  at the new cutoff? A revised earlier bar is a revision, not a new chronological
  event; a rolled window does not prove that a missing level disappeared.
- Does the observation support the original trigger, contradict the stated
  premise/invalidation condition, leave it pending, or supply conflicting evidence?
- Which conclusion or proposed component changes, why, and which parts remain
  unchanged? If a direction changes, explain the failed old premise and the
  independent support for the new one; there is no automatic opposite trade.

If the interval between cutoffs is missing, don't infer that an unobserved trigger
or invalidation never occurred. If a bar reaches both a proposed entry and a
stop/target, OHLC alone cannot establish their order, a real fill, or realized
profit/loss. State the observed price conditions and the uncertainty. Require
actual execution records for account/order-state claims and keep their analysis
with the execution/account owner. Calling an analytical premise contradicted is
not an instruction to close, reverse, cancel or replace an order.

No default persistence, refresh task, automatic expiry or account recovery is
needed. Return the revised reasoning in the current answer. A user-requested
saved artifact is a separately admitted effect, not permission to modify the
installed Skill or create an unsolicited experience database.

## Deliver the useful subset

For an actionable idea request, make the source/cutoff, premise and alternative,
trigger, supported price components, contradiction/wait conditions and material
execution gaps clear in the user's requested format. If only a trigger is
supportable, give that watch condition and say that entry/stop/target selection is
incomplete. Don't pad the result with invented levels or a second target.

For a supplied-plan review, preserve the original, identify supported/unsupported
components, show requested arithmetic, and explain changes without silently
turning review into a replacement plan. An observed trigger can be reported
without asserting trade permission; human confirmation remains necessary.

Source basis: numbered knowledge files 17 (stop/target reasoning), 22 (sourced
retest candidates) and 23 (projections), with the plan-invalidation questions in
`pa_agent/ai/decision_continuity.py` and signed-distance arithmetic in
`pa_agent/util/trade_metrics.py`. The source's RR caps, stop widening, compulsory
probability/targets, guessed ticks, CSV/state inference and fixed expiry/cooldown
are not retained. Revision/license scope is recorded in [README](../README.md);
the actual calculation grammar is in [measurements](measurements.md).
