# Coverage comparison: EP vs BVA vs CEG vs MC/DC on `pricing`

Task 2 of the TSS lab. Each technique's suite was run **separately** (fresh
pytest process and fresh coverage data per run — pytest-cov erases prior data
unless `--cov-append` is given, which was not used), then all four were run
together. Line% and branch% are split out of `coverage.json`
(`covered_lines/num_statements` and `covered_branches/num_branches`), because
the terminal report's single "Cover" column blends statements and branches.

## Measurement protocol

All commands run from the workspace root (`C:\Users\Prekzursil\.zcode\workspace\default`),
one fresh invocation per suite:

```
python -m pytest tss/lab/tests/test_ep.py   -q --cov=pricing --cov-branch --cov-report=term-missing --cov-report=json
python -m pytest tss/lab/tests/test_bva.py  -q --cov=pricing --cov-branch --cov-report=term-missing --cov-report=json
python -m pytest tss/lab/tests/test_ceg.py  -q --cov=pricing --cov-branch --cov-report=term-missing --cov-report=json
python -m pytest tss/lab/tests/test_mcdc.py -q --cov=pricing --cov-branch --cov-report=term-missing --cov-report=json
python -m pytest tss/lab/tests/test_ep.py tss/lab/tests/test_bva.py tss/lab/tests/test_ceg.py tss/lab/tests/test_mcdc.py \
              -q --cov=pricing --cov-branch --cov-report=term-missing --cov-report=json
```

Environment: Python 3.14.6, pytest 8.4.2, pytest-cov 7.1.0, coverage 7.15.2
(Windows). Measured module: `tss/lab/pricing.py` — 57 statements, 22 branch
destinations. The **only** exclusion is the defensive guard
`if total < 0:  # pragma: no cover` at `pricing.py:148-149`; the combined
JSON run reports `excluded_lines: [148, 149]` and no `.coveragerc`/`setup.cfg`
exists anywhere that could add further excludes (verified by directory check).

## Results

| Suite   | Tests | Passed | Line coverage            | Branch coverage            | Missing lines | Missing branch arcs |
|---------|------:|-------:|--------------------------|----------------------------|---------------|---------------------|
| EP      | 52    | 52     | **100.00%** (57/57)      | **100.00%** (22/22)        | —             | —                   |
| BVA     | 129   | 129    | 96.49% (55/57)           | 90.91% (20/22)             | 78, 85        | 77→78, 84→85        |
| CEG     | 17    | 17     | 98.25% (56/57)           | 95.45% (21/22)             | 78            | 77→78               |
| MC/DC   | 14    | 14     | **100.00%** (57/57)      | **100.00%** (22/22)        | —             | —                   |
| COMBINED| 212   | 212    | **100.00%** (57/57)      | **100.00%** (22/22)        | —             | —                   |

Raw `term` output per fresh run (combined "Cover" column, for the record):
EP `57 stmts, 0 miss, 22 branch, 0 BrPart → 100%`; BVA `2 miss, 2 BrPart → 95%`;
CEG `1 miss, 1 BrPart → 97%`; MC/DC `100%`; COMBINED `100%`, `212 passed in 1.71s`.

## Combined-run verdict and the gap-closing step

The combined suite **already reaches 100% line and 100% branch coverage** of
`pricing` (only the pragma-excluded guard at `pricing.py:148-149` remains
unmeasured, exactly as the lab contract allows). The conditional instruction
"if combined coverage is below 100%, add tests to the weakest suite" therefore
**did not trigger — no tests were added**, and the four suites are untouched.

For the record, the weakest single suite is **BVA** (96.49% line / 90.91%
branch). Had the gap-closing step been needed, its two holes are precisely
characterized below and would have been closed *in BVA character* only with
boundary-anchored probes (e.g. probing the composed VAT base at its
sign boundary *with* `apply_to_fee=True`, i.e. crossing base = 0 through the
fee summand instead of the shipping summand, which drives `pricing.py:85`
while remaining a value-neighborhood test; line 78, however, is not reachable
by any value boundary and would have to remain to another suite's credit).

## What each technique found and missed, and why

**EP — 100%/100% with 52 tests.** The equivalence-class table in `docs/ep.md`
partitions *every* input, including the booleans (`enabled`, both
`apply_to_*` flags, `vat_enabled`), the rounding-mode strings (each mode plus
the unrecognized-string class), and the error classes (Q-8/Q-9). Because every
decision in `pricing.py` is fed by exactly one of those partitioned inputs,
choosing one representative per class ends up taking every branch of every
guard. That is the expected character of EP done over the full input space:
*class representativeness* — the uncovered residue of a well-formed class
table is empty by construction. The price is breadth: it took 52 tests, and
EP's representatives say nothing about *neighborhoods* (that a 0.004 vs 0.005
flat fee flips the cent) — it just happens not to need them for coverage.

**BVA — 96.49%/90.91% (the weakest).** BVA's 129 tests are the deepest probes
of *numeric value boundaries* in the lab (cent ties per rounding mode, the
0.005 minimum-surviving-cent per clamp, sign crossings, override switch
points), and they fully cover every value-driven guard in
`quantize_money`, `compute_fee` and `compute_totals`. Its two misses are
exactly the two things boundary analysis has no lever on, both inside
`compute_vat`:

* `pricing.py:77-78` (`if not enabled: return 0.00`) — the disabled arm of
  `compute_vat` *as a direct call*. BVA drives VAT-disabled only through
  `compute_totals` (B19 row `en=False`), where the `vat_enabled=False` arm at
  `pricing.py:124-125` short-circuits *before* `compute_vat` is ever invoked,
  so line 78 never executes. An `enabled` flag has no value neighborhood, so
  no boundary probe can reach it.
* `pricing.py:84-85` (`if apply_to_fee: base += fee`) — BVA never sets
  `apply_to_fee=True` anywhere: its base-boundary sweeps (B12) cross zero via
  the *shipping* summand only. A boolean flag is again not a value with
  neighbors, so BVA's method has nothing to say.

This is the textbook signature of BVA: unbeatable *at the boundaries it
models*, structurally blind to boolean-gate combinations it does not model.

**CEG — 98.25%/95.45%.** The 17-column decision table covers every feasible
*condition combination* observable through `compute_totals` — including the
AND-gate subtleties (col 8: `apply_to_shipping=True` with non-positive
shipping adds nothing; col 9: `apply_to_fee=True` with a zero fee adds
nothing; col 14: both flags true yet base still 0). Its single miss is again
`pricing.py:77-78`, and the reason is architectural: the CEG modelled the
VAT-enabled gate at the *totals* level (cause C4 → effect E4), which the
implementation realizes as arm 1 at `pricing.py:124-125`. `compute_totals`
only ever calls `compute_vat` with `enabled=True`, so the callee's internal
`not enabled` guard is a redundant, unobservable-from-the-black-box decision —
no feasible decision-table column can reach it. CEG also, by explicit scope
discipline (its header note), pins `rounding="half_up"` everywhere: it leaves
the rounding-mode value space to EP/BVA entirely, yet still loses nothing on
coverage because rounding is not a branch, only a value transform.

**MC/DC — 100%/100% with only 14 tests.** The most coverage-efficient suite
by a wide margin (14 tests vs EP's 52). Each test executes both rows of one
minimal pair: the target condition flips, every other condition feeding the
same decision is held fixed. Since every guard in `pricing.py` is a
single-condition decision (`if` chains, not compound booleans), a complete
MC/DC pair set *is* exactly a complete branch-arc set — each condition's
True/False arcs both get taken, which subsumes condition coverage and branch
coverage. The two arcs BVA missed are MC/DC pairs P4
(`test_mcdc_c04_compute_vat_not_enabled`, `test_mcdc.py:84`) and P7
(`test_mcdc_c07_compute_vat_apply_fee`, `test_mcdc.py:168`) — precisely
because *condition independence* is what MC/DC exists to demonstrate: each
boolean input must be shown to independently change its decision's outcome,
so no gate can stay untested. The unreachable condition C15
(`total < 0`, `pricing.py:148`) correctly gets no pair (documented in
`docs/mcdc.md` §4), matching the pragma exclusion.

**Union.** The per-suite gaps (BVA's two, CEG's one) are all the *same* two
lines, both inside `compute_vat`, and both are covered by EP
(`test_v1_enabled_false_zero_regardless` at `test_ep.py:303` calls
`compute_vat(enabled=False)` directly; `test_v3_apply_fee_only`/
`test_v3_apply_both` at `test_ep.py:331-338` set `apply_to_fee=True`) and by
MC/DC (pairs P4 and P7). Hence the union closes to 100%/100% with no additions
needed; in fact the EP ∪ MC/DC union alone already achieves it.

## Technique-vs-coverage takeaway

* **BVA on boundaries**: confirmed — it is the only suite that pins *every*
  rounding mode's tie behavior and every clamp's minimum-surviving cent, but
  it is the weakest on branch coverage because boolean gates have no
  boundary values.
* **CEG on condition combinations**: confirmed — it is the only suite that
  proves the *joint* behavior of flags (AND-gates where a flag is true but
  its summand contributes nothing), at 17 tests for near-complete coverage;
  its one miss is a guard made unobservable by the implementation's call
  structure, not by the table.
* **MC/DC on condition independence**: confirmed — cheapest route to full
  branch coverage (14 tests); each boolean's independent effect is asserted
  as a before/after pair, which mechanically takes both arcs of every guard.
* **EP on class representativeness**: confirmed — a complete class table over
  all inputs (values, booleans, strings, error classes) yields 100% with one
  representative per class, at the cost of the most tests and zero
  neighborhood information.
* Coverage number alone is a weak proxy for technique value: BVA's 129 tests
  found nothing MC/DC's 14 didn't cover, yet they pin cent-tie behavior under
  all four rounding modes that no other suite checks. The percentages measure
  *code* reachability; the techniques differ in the *input-space* claims they
  certify.
