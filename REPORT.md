# REPORT — TSS Lab: black-box test design for the `pricing` module

Assembled 2026-10-17 from [`README.md`](README.md), [`AI_USAGE.md`](AI_USAGE.md),
[`SPEC.md`](SPEC.md) and the derivation docs in [`docs/`](docs/). Module under
test: [`pricing.py`](pricing.py) — a pure-stdlib (`decimal` + `dataclasses`)
port of the team's own `momentstudio` production module, behavior-identical
(README.md:5-11). The specification post-dates the code (spec-after-code
provenance is stated openly in README.md:13-22 and SPEC.md); all four suites
are derived from the SPEC, not from the implementation.

**Verification re-run at assembly time (this session, 2026-10-17).** Three
gate commands were re-executed from the workspace root; all three passed:

| Command (run this session) | Result |
|---|---|
| `python -m pytest tss/lab -q --cov=pricing --cov-branch --cov-fail-under=100` | `212 passed in 0.76s`; `pricing.py 57 Stmts, 0 Miss, 22 Branch, 0 BrPart, 100%`; `Required test coverage of 100% reached` |
| `python tss/lab/docs/gen_cfg.py` | `ALL CHECKS PASSED (0 checks failed)`, exit 0; **69** `PASS` lines (counted via `grep -c "^PASS"`) |
| `python tss/lab/mutants/run_demo.py` | `DEMO RESULT: ALL CLAIMS MATCH (kill / survive / equivalence demonstrated)`, exit 0 |

Per-suite coverage splits and the mutation-testing runs are cited from their
docs (protocol and receipts embedded there); they were **not** re-executed at
assembly time.

---

## Executive summary — tasks 1–7 → artifacts → headline numbers

| # | Task | Primary artifacts | Headline numbers |
|---|---|---|---|
| 1 | Program + requirements | `pricing.py` · `SPEC.md` | 4 public functions + `PricingBreakdown`; 57 statements / 22 branches; SPEC v1: 9 sections, rule families R1–R4, F1–F5, V1–V5, T1–T8, E1–E4 |
| 2 | Coverage measurement & comparison | `docs/coverage-comparison.md` | Per-suite line/branch: EP **100/100%**, BVA **96.49/90.91%**, CEG **98.25/95.45%**, MC/DC **100/100%**; combined **212 tests, 100% line + 100% branch** (gate re-run green this session) |
| 3 | CFG, V(G), basis paths | `docs/cfg.drawio` · `docs/cfg.svg` · `docs/cfg-analysis.md` · `docs/gen_cfg.py` | 51 nodes, 62 control edges (+11 call edges, excluded from V(G)); V(G) = 1/4/6/8 per function, module V = 62−51+2·4 = **19**; **19-path basis** covering all 62 edges; verifier: **69 machine checks, 0 failures** |
| 4 | Test-design techniques (EP / BVA / CEG / MC-DC) | `tests/test_ep.py` + `docs/ep.md` · `tests/test_bva.py` + `docs/bva.md` · `tests/test_ceg.py` + `docs/ceg.md` · `tests/test_mcdc.py` + `docs/mcdc.md` | **52 / 129 / 17 / 14 tests** (Σ 212, all green); EP: full partition tables w/ traceability; BVA: boundaries B1–B20, 3- and 5-point neighbor sets; CEG: 12 causes + 2 derived, 10 effects, 17 feasible columns (8 impossible combos struck); MC/DC: 15 conditions, 14 minimal pairs, 1 unreachable (C15) |
| 5–6 | Hand mutants: killed / surviving / equivalent + demo | `mutants/mutant_{equivalent,killed,surviving}.py` · `mutants/run_demo.py` · `docs/mutants-manual.md` | 3 order-1 mutants — **EQUIVALENT** (L148 `<`→`<=`, proven), **KILLED** (L59 `==`→`!=`, by chosen test), **SURVIVING** (L57 `<=0`→`<=4`, survives chosen test, dies to full suite); demo: `ALL CLAIMS MATCH` (re-run green this session) |
| 7 | Mutation testing, two tools, analysis | `docs/mutation-analysis.md` | mutmut 3.8.0 (**176** mutants): EP 75.57% · BVA 77.84% · CEG 66.48% · MC/DC 61.36%; cosmic-ray 8.7.0 (**226** mutants): EP 82.30% · BVA 88.05% · CEG 80.97% · MC/DC 81.42%; `pricing.py` md5 unchanged across all 8 runs |

AI assistance for every deliverable is itemized per the required
tool/purpose/prompt/result/edits/validation format in [`AI_USAGE.md`](AI_USAGE.md)
(11 logged uses, incl. the round-1 critic fix pass, AI_USAGE.md:24-143). The
per-member contribution declaration in README.md:113-131 is a placeholder
(`FILL IN BEFORE SUBMISSION`) — team-owned, intentionally not filled here.

---

## Task 1 — Program + requirements

- **Program**: `pricing.py` — the whole module declared as analysis scope:
  `quantize_money`, `compute_fee`, `compute_vat`, `compute_totals` plus the
  frozen `PricingBreakdown` record (README.md:5-8). Size: **57 statements,
  22 branch destinations** (README.md:83-84; confirmed live by this session's
  coverage run: `57 Stmts / 22 Branch`). Port of the team's own
  `momentstudio/backend/app/services/pricing.py`, fetched 2026-10-16,
  behavior-identical, stdlib-only (README.md:9-11).
- **Requirements**: `SPEC.md` v1 — black-box only (no implementation detail);
  **9 sections, rules R1–R4 (quantization/rounding), F1–F5 (fee), V1–V5 (VAT),
  T1–T8 (totals), E1–E4 (errors)** (AI_USAGE.md:42). Every SPEC rule is
  exercised by at least one suite test; the 100%-branch combined run is the
  machine check that the rules cover all reachable behavior (AI_USAGE.md:44).
- **Provenance, stated plainly**: the program pre-dates the lab (team's own
  code), so the SPEC was derived from the module's observed behavior, not
  written before it; the README relies on transparent provenance + black-box
  spec character + suites derived from SPEC rather than code (README.md:13-22).

## Task 2 — Coverage measurement and comparison

Source: `docs/coverage-comparison.md` (protocol at lines 10-29, results table
at lines 33-39). Each suite was run separately (fresh pytest process + fresh
coverage data), line%/branch% split out of `coverage.json`; environment
Python 3.14.6 / pytest 8.4.2 / pytest-cov 7.1.0 / coverage 7.15.2. Only
exclusion: the `# pragma: no cover` defensive guard at `pricing.py:148-149`.

| Suite | Tests | Line coverage | Branch coverage | Missing |
|---|---:|---|---|---|
| EP | 52 | **100.00%** (57/57) | **100.00%** (22/22) | — |
| BVA | 129 | 96.49% (55/57) | 90.91% (20/22) | lines 78, 85; arcs 77→78, 84→85 |
| CEG | 17 | 98.25% (56/57) | 95.45% (21/22) | line 78; arc 77→78 |
| MC/DC | 14 | **100.00%** (57/57) | **100.00%** (22/22) | — |
| **Combined** | **212** | **100.00%** | **100.00%** | — |

- The combined run already reaches 100%/100%, so the conditional
  gap-closing instruction ("add tests to the weakest suite") **did not
  trigger — no tests added** (coverage-comparison.md:45-51). Weakest suite:
  BVA; its two holes are boolean-gate arcs inside `compute_vat` that value
  boundaries cannot reach (lines 78, 85 — analysis at
  coverage-comparison.md:76-97).
- Why the techniques differ: EP = class representativeness (100% at the cost
  of 52 tests, zero neighborhood info); BVA = unbeatable at value/cent-tie
  boundaries, blind to boolean gates; CEG = joint flag combinations (AND-gate
  subtleties cols 8/9/14), one miss is a guard made unobservable by call
  structure; MC/DC = cheapest full branch coverage (14 tests) because every
  guard in the module is single-condition (coverage-comparison.md:62-159).
- **Live receipt (this session)**: the gate command re-run printed
  `212 passed`, `100%`, `Required test coverage of 100% reached`.

## Task 3 — Control-flow graph, V(G), basis paths

Sources: `docs/cfg-analysis.md` (construction lines 10-60, V(G) lines 177-201,
basis lines 203-265, infeasible guard lines 267+), `docs/cfg.drawio` (real
draw.io XML, 130 mxCells per AI_USAGE.md:97), `docs/cfg.svg` (rendered),
`docs/gen_cfg.py` (generator + verifier).

- **Graph**: 51 numbered nodes `N1..N51` in four function bands
  (quantize 3, fee 9, vat 14, totals 25); **62 solid control edges** labeled
  T/F at decisions; **11 dashed interprocedural call edges**, excluded from
  V(G) per McCabe's intra-procedural definition (cfg-analysis.md:11, 40-51).
- **Cyclomatic complexity** V(G) = E − N + 2P (cfg-analysis.md:182-195):

  | Function | E | N | V(G) | cross-check (decisions+1) |
  |---|---:|---:|---:|---|
  | `quantize_money` | 2 | 3 | **1** | 0+1 |
  | `compute_fee` | 11 | 9 | **4** | 3+1 |
  | `compute_vat` | 18 | 14 | **6** | 5+1 |
  | `compute_totals` | 31 | 25 | **8** | 7+1 |
  | **Module** (P=4) | **62** | **51** | **62−51+8 = 19 = 1+4+6+8** | 15 decisions total |

- **Basis**: 19 linearly independent paths (1+4+6+8) whose union covers **all
  62 control edges** (2/2, 11/11, 18/18, 31/31); GF(2) rank of the
  path×edge incidence matrix equals V(G); 18 of the paths were additionally
  executed under `sys.settrace` and matched their documented node sequences
  (cfg-analysis.md:203-211). 60 of 62 edges are reachable by executable
  inputs; the 2 edges of the defensive guard (E58/E60, `total < 0`) are
  unreachable — a 5400-combination exhaustive sweep never yields a negative
  total — so basis path T-P8 is structural only (cfg-analysis.md:263-266;
  verifier output this session: `PASS infeasibility: … sweep … never yields
  total < 0`).
- **Machine verification (re-run this session)**: `python
  tss/lab/docs/gen_cfg.py` re-parses the written `cfg.drawio`, recounts E/N
  per band, cross-checks V(G) against an AST decision count, verifies basis
  validity/edge coverage/GF(2) rank and the traced paths → **69 PASS lines
  (counted), `ALL CHECKS PASSED (0 checks failed)`, exit 0**.

## Task 4 — Test-design techniques: EP, BVA, CEG, MC/DC

All four suites derive from `SPEC.md` (not the code), use exact `Decimal`
equality assertions, and pin SPEC R1's two-decimal shape via
`as_tuple().exponent == -2`. Combined: **212 tests, all green** (re-run this
session), **100% line + branch** combined.

### 4.1 Equivalence partitioning — `tests/test_ep.py` (52 tests) + `docs/ep.md`
- Partition tables cover every input: rounding modes (R-1…R-10 incl.
  unrecognized-string and default-arg classes), `quantize_money` value and
  invalid classes (Q-1…Q-9 incl. E3 error classes), `fee_type` (T-1…T-3),
  enabled flags (E-1…E-4), apply-flag combinations (A-1…A-5), money sign /
  zero / precision classes (M-1…M-23, with SPEC-declared ≤0 merges evidenced
  by zero+negative representatives), rate classes (VR-1…VR-4), composition /
  record classes (C-1…C-4) — `docs/ep.md` §1.1–1.8.
- Inventory: 14 quantize + 10 fee + 10 vat + 18 totals tests; every class row
  has ≥1 test, and no test leaks into BVA/CEG/MC-DC space (ep.md:141-150).
- Coverage: 52 tests → **100% line, 100% branch** alone
  (coverage-comparison.md:35).

### 4.2 Boundary value analysis — `tests/test_bva.py` (129 tests) + `docs/bva.md`
- Domain has no finite upper bound, so the classic 5-point pattern is applied
  where meaningful: 3-point sets {B−, B, B+} at clamp/sign boundaries (step
  0.001 / 0.01 / 1) and 5-point tie sets {x.xx4, x.xx49, x.xx5, x.xx51,
  x.xx6} at cent ties; cent-quantum boundary {0.004, 0.005, 0.006}
  (bva.md:11-33).
- Boundary inventory **B1–B20**: per-rounding-mode tie tables (B1–B4,
  positive/negative mirrors, half_even even/odd pairs, smallest surviving
  cent), 2-dp shape + idempotency over six representatives (B5), and clamp /
  switch-point boundaries through `compute_totals` (B6–B20, e.g. B17 subtotal
  sign boundary, B19 override-vs-computed switch points, B20 minimal-sum
  totals).
- Coverage: 129 tests → 96.49% line / 90.91% branch — the weakest suite, by
  construction blind to the two boolean-gate arcs in `compute_vat`
  (coverage-comparison.md:36, 76-97).

### 4.3 Cause–effect graph + decision table — `tests/test_ceg.py` (17 tests) + `docs/ceg.md`
- **12 SPEC causes (C1–C12) + 2 derived sign conditions (X1, X2)**, **10
  effects (E1–E10)** incl. the total-identity invariant E10 asserted in every
  test; boolean equations for the graph in ceg.md §3.1, diagram in §3.2.
- Constraints: **8 impossible combinations explicitly struck** (ceg.md:175-203),
  e.g. `¬C4 ∧ (E5/E6)` (disabled VAT ignores override), `¬X2 ∧ E9` (floor is
  definitionally tied to X2).
- Restricted-entry decision table: **17 feasible columns → exactly 17 tests**
  (`test_col_01`…`test_col_17`, traceability in ceg.md §4); covers the joint
  flag behavior no other technique pins (col 8: shipping flag true but
  shipping ≤ 0 adds nothing; col 9: fee flag true but zero fee adds nothing;
  col 14: both flags true yet base 0; col 17: negative subtotal reported
  as-is, taxable floored, total ≥ 0).
- Coverage: 17 tests → 98.25% line / 95.45% branch; the single miss
  (`pricing.py:78`) is unobservable through the black-box call structure
  (coverage-comparison.md:99-111).

### 4.4 MC/DC — `tests/test_mcdc.py` (14 tests) + `docs/mcdc.md`
- Complete condition inventory: **15 conditions C1–C15** across the three
  functions with file:line locations (mcdc.md:25-42); `quantize_money` has no
  conditions (branch-free `dict.get` fallback, mcdc.md:16-19).
- **C1–C14 each exercised by one minimal pair → 14 tests** (mcdc.md:43).
  **C15 (`total < 0`, pricing.py:148) is unreachable** and correctly gets no
  pair (mcdc.md §4), matching the pragma exclusion.
- Because every decision in the module is single-condition, the complete
  MC/DC pair set *is* a complete branch-arc set: **14 tests → 100% line +
  100% branch** — the most coverage-efficient suite by a wide margin
  (coverage-comparison.md:113-127).

## Tasks 5–6 — Hand-built mutants: killed / surviving / equivalent + demonstration

Source: `docs/mutants-manual.md` (summary table lines 6-10, equivalence proof
§2, kill/survive transcripts §3, demo output §4) + `mutants/`.

Three order-1 mutants, each exactly one line changed from `pricing.py`
(diff receipts in the doc):

| Mutant | File | Line | Change | Verdict |
|---|---|---|---|---|
| Equivalent | `mutants/mutant_equivalent.py` | 148 (final clamp) | `if total < 0:` → `if total <= 0:` (relational `<`→`<=`) | **EQUIVALENT** — written proof (mutants-manual.md §2); even with the mutated branch firing (total == 0), all 7 breakdown fields identical; full-suite survival (212 passed) is forced by the proof, not luck |
| Killed | `mutants/mutant_killed.py` | 59 (C3) | `== "percent"` → `!= "percent"` (relational `==`→`!=`) | **KILLED by the chosen test**; non-equivalence witnessed in-process (`original=10.00 mutant=5.00`) |
| Surviving | `mutants/mutant_surviving.py` | 57 (C2) | `fee_value <= 0` → `fee_value <= 4` (boundary constant shift) | **SURVIVES the chosen test, KILLED by the full suite**; non-equivalence witnessed (`original=2.00 mutant=0.00` for flat fee 2 ∈ (0,4]) |

**Demonstration (re-run this session)**: `python tss/lab/mutants/run_demo.py`
runs the chosen MC/DC test case and the full suite against each mutant in
isolated sandboxes and checks every verdict against the documented claims —
output tail: `DEMO RESULT: ALL CLAIMS MATCH (kill / survive / equivalence
demonstrated)`, exit 0 (full transcript in mutants-manual.md §4, lines
169-214).

## Task 7 — Mutation testing with two tools × four suites

Source: `docs/mutation-analysis.md` (environment/protocol lines 5-83, results
lines 85-106, analysis lines 108-148). Score convention: **killed /
(killed + survived)**; zero timeouts/suspicious/skipped in every run; every
run on scratch copies with `pricing.py` md5 `6d716bcc5d258808c8b2ec98aaf550d9`
verified unchanged before/after (mutation-analysis.md:28, 79-80, 251).

- **Tools**: mutmut 3.8.0 (refuses native Windows — `os.fork()` — so run in
  WSL Ubuntu, Python 3.12.3, fresh venv; install hurdle documented) and
  cosmic-ray 8.7.0 (Windows Python 3.14.6). Clean-suite sanity runs per
  scratch dir (52/129/17/14 passed) preceded every mutation run
  (AI_USAGE.md:132).

| Tool | Suite | Killed | Survived | Total | Mutation score |
|---|---|---:|---:|---:|---:|
| mutmut 3.8.0 | EP | 133 | 43 | 176 | **75.57 %** |
| mutmut 3.8.0 | BVA | 137 | 39 | 176 | **77.84 %** |
| mutmut 3.8.0 | CEG | 117 | 59 | 176 | **66.48 %** |
| mutmut 3.8.0 | MC/DC | 108 | 68 | 176 | **61.36 %** |
| cosmic-ray 8.7.0 | EP | 186 | 40 | 226 | **82.30 %** |
| cosmic-ray 8.7.0 | BVA | 199 | 27 | 226 | **88.05 %** |
| cosmic-ray 8.7.0 | CEG | 183 | 43 | 226 | **80.97 %** |
| cosmic-ray 8.7.0 | MC/DC | 184 | 42 | 226 | **81.42 %** |

- **Findings** (mutation-analysis.md:108-148): BVA is the best suite under
  both tools (its sub-cent probes kill comparison-operator mutants); EP
  second; CEG and MC/DC trail with their order flipping between tools — a
  tool-operator effect, not test quality: MC/DC's minimal pairs hold other
  conditions fixed, so mutants that only misbehave under non-neutral settings
  survive mutmut, while cosmic-ray cannot generate string/default mutants at
  all. Absolute cosmic-ray scores run ~5–20 points higher partly because its
  extra 50 mutants include gross ones (e.g. type-annotation `BitOr → *`).
- The hand-proven equivalent mutant of tasks 5–6 is the analytic anchor for
  reading these survivor lists: equivalence must be proven, not assumed
  (mutants-manual.md:124-126).

---

## Reproduction

```bat
cd <workspace root>
python -m pytest tss/lab -q                                                 :: 212 passed (re-run 2026-10-17)
python -m pytest tss/lab -q --cov=pricing --cov-branch --cov-fail-under=100 :: 100%, exit 0 (re-run 2026-10-17)
python tss\lab\docs\gen_cfg.py                                              :: 69 PASS lines, exit 0 (re-run 2026-10-17)
python tss\lab\mutants\run_demo.py                                          :: ALL CLAIMS MATCH, exit 0 (re-run 2026-10-17)
```

Per-suite coverage protocol (fresh process per suite) and the mutmut /
cosmic-ray runbooks are embedded verbatim in `docs/coverage-comparison.md`
(lines 15-22) and `docs/mutation-analysis.md` (lines 25-83) respectively.
