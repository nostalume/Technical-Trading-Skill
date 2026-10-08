# Context and event sequences

Use this reference to interpret trend/range structure, channels, spikes, EMA
relationships, and breakout/test/failure sequences. Describe an interval-bound
hypothesis rather than selecting a mandatory market-state enum.

## Context is an observation relation

Identify the interval being explained and the boundary/sequence that supports the
interpretation. Highs and lows of all supplied bars form an **observed envelope**;
that alone does not establish a repeatedly defended trading range. A sequence of
successively higher closes is not an alternating higher-high/higher-low swing
structure. Local pivot measurements do not automatically choose meaningful swings.

| Reading | Observable support to discuss | Material alternative or counterevidence |
| --- | --- | --- |
| Directional trend/leg | Displacement through prior prices, directional closes, identifiable advances and retreats, response to opposing tests. | Repeated overlap, failed continuation, renewed two-sided traversal, or a boundary test inside a larger structure. |
| Tight channel | Sustained directional progress with comparatively limited retreats and coherent boundary anchors. | Apparent tightness from too short a sample, missing observations, or one isolated large bar. |
| Broad channel / stairs | Directional swing progression plus substantial retracement and overlap; explicit candidate channel anchors. | A sloping range with unstable boundaries, or direction that depends on which endpoints were selected. |
| Range / tight range | Repeated traversal and identifiable boundary tests; overlapping swings and conflicting directional attempts. | A pause within a directional leg or an envelope not yet tested on both sides. |
| Spike / accelerated move | Directional displacement compared with an explicit local baseline, limited overlap/retreat, boundary crossing if one exists. | One exceptional bar, a transient excursion, or a continuing move without evidence of acceleration. |

These readings can overlap. Do not count supporting descriptions as independent
votes. Report the raw relationships, how well they fit the selected interval,
and what they cannot discriminate. There is no automatic trend/range, spike,
Always In, or barbwire classifier in the bundle.

### Channels and scale conflicts

For a channel claim, identify the chosen low/high anchors, their ordering, and
how intervening prices interact with the candidate lines. Do not draw a channel
merely because two extrema exist. Chart angles depend on axis scaling; "45
degrees" is not a portable measurement. A redrawn line changes the proposed
baseline; preserve the earlier baseline for an earlier event assessment.

Retracement, overlap, and boundary stability can qualify tight vs broad without
old 30/50/78.6 percent bins. If computing retreat depth, state the completed move
and retreat endpoints; `window.net_close_change` and envelope width are not
maximum drawdown or a retreat-depth algorithm.

A recent upward leg can coexist with a broader downward sequence. Explain both
sample intervals and what that conflict changes; don't automatically declare
the recent leg a confirmed reversal or give either scale unconditional priority.
An upward channel is not universally a bearish flag: that reading needs an
identified broader downward hypothesis and a relation to it.

### Spikes, pauses, and exhaustion

Keep acceleration, a price breakout, an opening gap, and suspected exhaustion
distinct. A sharp move can pause, continue, broaden into a channel/range, or
reverse. Discuss which observations favor each relevant path, without imposing
bar-count rules, fixed overlap limits, Fibonacci state changes, or probabilities.

Increasing tails, reduced additional progress, overlap, or opposing closes can
support an exhaustion hypothesis. They may also reflect a normal pause. Deep
retracement alone does not establish an enduring reversal; inspect the response
at the selected origin/extreme and subsequent resumption attempts. Missing later
evidence remains missing, not exhaustion confirmation.

Descriptions such as urgency, trapped traders, liquidation, or institutional
buying are explanatory hypotheses unless separately evidenced. OHLC cannot
identify participant inventory or prove stop concentrations. Do not turn a large
range into a factual account of those mechanisms.

## EMA and gap language

Separate close-to-EMA position from whole-bar position. A close above the EMA can
occur while the bar intersects it. For an aligned EMA value E, a whole bar is
above if L>E, below if H<E, and touching/intersecting otherwise. The script uses
these neutral geometric names rather than inferring a bullish/bearish setup.

The source's **Always In Long/Short (AIL/AIS)** describes an interpretation of
directional persistence, not an instruction to hold a perpetual position. Discuss
directional progress, retreats, failed opposing attempts, and the actual
observation interval. EMA position alone or a fixed vote does not establish it.

**20GB (twenty gap bars)** is source terminology for a stretch of bars not touching
an EMA. Its number is not a trading threshold. Report actual same-side count,
indicator method/period, continuity, and `ema_gap_extent`: a left-truncated or
indicator-interrupted stretch can be only a lower bound. First contact with the
EMA can be a test hypothesis, not a guaranteed bounce or mean-reversion signal.

The source's context-specific **moving-average gap bar** can describe an entire
bar on the opposing side of the EMA during a pullback. State both geometric side
and contextual direction to avoid confusing it with same-side separation.

An **opening gap** instead compares an opening price with a named earlier
reference/session. A missing bar or missing session identity is not proof of a
gap; an EMA gap is not an opening gap.

## Breakouts are time-bound events, not permanent labels

Choose the reference before the event: a supplied level, prior-bar envelope,
identified swing, or explicitly anchored line. A line needs its value at the
event time; `compare` only compares a selected prior H/L envelope. Do not use
`window`, which includes the target bar, as proof that the target exceeded a
pre-existing boundary. Keep the selection rationale visible rather than fitting
a boundary after observing the outcome.

Distinguish the following observations without forcing a fixed ladder:

1. **Excursion:** a high/low crosses the prior reference. A close may remain inside.
2. **Close beyond:** a closed bar ends beyond that reference. A forming close is
   provisional, and equality is not a strict crossing.
3. **Later response:** later identified bars extend, overlap, return, or test the
   boundary. Report their order and the cutoff. A completed event can be followed
   by contradictory evidence; don't erase it by retaining only a newer label.
4. **Test:** price returns to a named level/zone and shows a specified response.
   Contact alone does not prove a successful retest or future continuation.
5. **Failure / failed failure:** a previously stated continuation premise is
   contradicted; a subsequent attempt to reverse that event can itself be
   contradicted. Identify each premise and observation before using these terms.

No immediate continuation is insufficient evidence by itself to call an attempt
failed. A later close back inside can contradict a "remain outside" premise
without proving a lasting reversal. Both extremes can cross on one outside bar;
OHLC does not reveal crossing order or authorize both directions.

Old `testing/surviving` labels and target permissions are excluded. An event's
support comes from its actual observations, not a state enum or a fixed number
of follow-through bars. A geometric measured move can be calculated separately
without claiming the event has succeeded.

## Repeated overlap and interior signals

**Tight trading range (TTR)** and **barbwire** are descriptive source terms for
compressed, repeatedly overlapping, directionally ambiguous behavior. The script
measures adjacent range intersection divided by the pair's envelope; it does not
measure average swing height, participant conflict, or a density/quality score.
Neither high overlap nor an inside sequence automatically declares a no-trade
zone. Explain why evidence for the requested directional claim is weak, and
whether a boundary event or different interval could distinguish it.

An interior signal has no automatic access to the whole envelope as profit
potential. Identify nearer conflicting structure if supplied. It can still be
explained without imposing the old ban on all middle-range activity.

Historical failed-signal prices can be **retest candidates** (source term:
magnet). Name the source and later response; proximity is not proof that price
will be attracted there or that trapped positions exist. Do not import fixed
tick-based trap templates across products.

Source basis: the repository's diagnostic framework, bull/bear channel and spike
recognition/strategy material, range recognition/strategy material, and numbered
files 13, 18, 20, 21, and 22. Fixed state routes, numerical gates, current-market
claims, empirical percentages, and participant stories presented as fact are
not retained. See [README](../README.md) for revision and licensing scope.
