# Candles and repeated tests

Use this reference for bar geometry, bar roles, adjacent relationships, and
first/second-attempt terminology. It does not assign an entry permission.

## Geometry is not a role

For OHLC, range is H-L, body is |C-O|, upper wick is H-max(O,C), lower wick is
min(O,C)-L, and close position is (C-L)/(H-L). Report the denominator and interval
when comparing proportions. A flat range makes these proportions undefined, not
evidence of weak or strong buying.

The same upward-closing bar can be a continuation, a boundary test, a rebound
within a decline, or an unfinished attempt. Describe its body, tails, close, and
location before interpreting it as a trend or reversal bar. A long wick records
an excursion and subsequent closing position; it does not identify who traded,
why they traded, or how much liquidity remains there.

Keep these roles separate, even when one bar performs more than one:

- **Structure observation:** helps define an existing boundary or sequence.
- **Signal candidate:** suggests a hypothesis tied to that structure.
- **Trigger observation:** reaches the stated price condition for that hypothesis.
  This is a price event, not a filled order.
- **Follow-through observation:** arrives later and supports or contradicts the
  proposed movement. It cannot be borrowed at the signal's earlier cutoff.

Evaluate an apparently directional bar against its actual context: displacement
vs overlap, boundary vs interior, trend continuation vs opposing test, and later
evidence if available. Do not classify using old body/wick percentage thresholds
or call a small numerical threshold crossing a change in trading permission.

## Inside, outside, and sequence relationships

The script uses inclusive range relations:

- inside: current H <= previous H and current L >= previous L;
- outside: current H >= previous H and current L <= previous L.

Equal ranges satisfy both; report `equal_range` rather than forcing an exclusive
label. An outside range does not disclose whether the high or low occurred first.
It can expose competing directions without resolving either.

The script's `ii`, `iii`, and `ioi` are, respectively, two inside relations, three
inside relations, and inside-outside-inside relations. They require a base bar:
three, four, and four supplied observations. Do not confuse the number of named
relations with the number of prices inspected. They require declared continuity;
otherwise they are unavailable, not false.

Contraction after a directional leg and contraction in a repeatedly crossed
range can have identical inside-bar geometry. The former can support a pause/
continuation hypothesis; the latter can leave direction unresolved. An outside
bar followed by contraction can support a boundary-test narrative, but neither
an `ioi` label nor overlap alone establishes which boundary will break next.

**Two-bar reversal (2BR):** an opposing pair can suggest rejection of the first
bar's move. Identify the two bars, their price coverage and closes, prior context,
and later response. An opposing color pair alone does not establish a major
trend reversal. Automated 2BR quality and micro-double classification are not
implemented; do not convert raw geometry into those classifier outputs.

## Repeated attempts: specify what was tried

A second test is meaningful only relative to an identified first attempt and
the reaction between them. Name the shared level or hypothesis, first attempt,
intervening retreat, second attempt, and current cutoff. Two adjacent highs are
not automatically two attempts at the same setup. A second test supplies new
observations but can also reveal deterioration or continuation through the level;
it is not intrinsically more profitable than the first.

For this repository-derived terminology:

| Term | Conditional reading |
| --- | --- |
| H1 | In an upward-context pullback, the first resumption attempt after the first retreat leg, with a price trigger above the preceding bar's high. |
| H2 | A further retreat/resumption sequence supplies a second attempt at that upward-context hypothesis, again referencing the preceding bar's high. |
| L1 | In a downward-context rebound, the first resumption attempt after the first rebound leg, with a price trigger below the preceding bar's low. |
| L2 | A further rebound/resumption sequence supplies a second attempt at that downward-context hypothesis, again referencing the preceding bar's low. |

These are contextual descriptions, not cumulative counts of every higher high
or lower low. Trace the retreat legs and trigger bars. A new swing, a sustained
break of the old hypothesis, or a changed contextual direction can make the old
count inapplicable; explain the reset premise instead of applying an automatic
ATR threshold. If the legs or reset are ambiguous, describe the visible test and
leave the H/L label tentative. Full automatic H/L counting remains excluded.

H2/L2, a second test of a range boundary, and a second reversal attempt are not
synonyms. Use the actual event relation; don't force one label onto all of them.
The absence of subsequent bars leaves follow-through pending. Subsequent mixed
evidence should remain mixed, not become "yes" because one bar advanced.

## Review contrasts

- A large upward body near an established upper boundary can be a breakout
  attempt; the identical bar inside an envelope is not a breakout of that envelope.
- A pair of near-equal lows can be a micro-double candidate, but "near" needs an
  explicit comparison scale/tolerance if a categorical claim depends on it. No
  tick, ATR tolerance, or automatically valid support is inferred.
- A visible second attempt can still lack a trigger or later response. Name the
  completed components and pending component, not a completed trade signal.

Source basis: the repository's bar-by-bar checklist and numbered knowledge files
15 (second entries), 16 (bar signals), and 19 (H/L counting), together with
`pa_agent/ai/kline_features.py`. Definitions are rewritten; old win rates,
fixed retry limits, quality gates, direction bans, and schema requirements are
not carried over. Source revision and license are recorded in [README](../README.md).
