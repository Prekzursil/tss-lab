# TSS Lab — Black-box test design for the `pricing` module

## Scope declaration

Per the assignment note, the **analysis scope is declared as the whole
`pricing` module** — the four public functions `quantize_money`,
`compute_fee`, `compute_vat`, `compute_totals` plus the `PricingBreakdown`
record (~4 functions). The module is a pure-stdlib
(`decimal` + `dataclasses`) port of the team's own repository code
(`momentstudio/backend/app/services/pricing.py`, fetched via GitHub API on
2026-10-16); behavior is identical, so results transfer to the original.

**Provenance, stated plainly.** The assignment asks for a program *and* its
requirements. Here the program pre-dates the lab (it is the team's own
production code), so [`SPEC.md`](SPEC.md) was derived by observing that
module's behavior rather than written before it. The assignment note permits
declaring a bounded scope; it does not by itself authorize spec-after-code
reuse — we rely instead on the transparent provenance above, on the fact that
the specification is written purely in black-box terms (no implementation
detail) and that every suite below is derived from the SPEC, not from the
code. AI tooling usage across all deliverables is logged in
[`AI_USAGE.md`](AI_USAGE.md).

- Requirements baseline: [`SPEC.md`](SPEC.md) — black-box specification
  (inputs, domains, rounding, fee/VAT/totals composition, error behavior).
  All four suites are derived from it, not from the implementation.

## Layout

```
tss/lab/
├── pricing.py        # module under test (ported, behavior-identical)
├── SPEC.md           # black-box requirements specification (derivation source)
├── README.md         # this file
├── AI_USAGE.md       # AI usage log: tool/purpose/prompt/result/edits/validation per deliverable
├── pyproject.toml    # pytest + coverage configuration
├── tests/
│   ├── conftest.py   # puts tss/lab on sys.path so `import pricing` works
│   ├── test_ep.py    # equivalence partitioning suite      (52 tests)
│   ├── test_bva.py   # boundary value analysis suite       (129 tests)
│   ├── test_ceg.py   # cause–effect graph / decision table  (17 tests)
│   └── test_mcdc.py  # modified condition/decision coverage (14 tests)
├── docs/
│   ├── ep.md                 # EP derivation (partition tables + traceability)
│   ├── bva.md                # BVA derivation (boundary tables B1–B20+)
│   ├── ceg.md                # CEG graph + restricted-entry decision table
│   ├── mcdc.md               # MC/DC derivation (condition pairs, truth tables)
│   ├── coverage-comparison.md  # per-suite vs combined coverage (point 2)
│   ├── cfg.drawio / cfg.svg  # control-flow graph (real draw.io XML + rendered SVG)
│   ├── cfg-analysis.md       # CFG construction, V(G), 19-path basis, infeasible-path analysis
│   ├── gen_cfg.py            # CFG generator + verifier (69 machine checks)
│   ├── mutants-manual.md     # the three hand mutants, equivalence proof, demo transcript
│   └── mutation-analysis.md  # mutmut + cosmic-ray × 4 suites: scores, survivors (point 7)
└── mutants/
    ├── mutant_equivalent.py  # order-1 mutant: final clamp `<` → `<=` (proven EQUIVALENT)
    ├── mutant_killed.py      # order-1 mutant: `fee_type == "percent"` → `!=` (KILLED)
    ├── mutant_surviving.py   # order-1 mutant: `fee_value <= 0` → `<= 4` (SURVIVES chosen test)
    └── run_demo.py           # sandboxed demo: chosen test + full suite per mutant, verdict checks
```

## Running

Run everything (all suites):

```
python -m pytest tss/lab -q
```

Run the coverage gate (all suites, branch coverage, must reach 100 %):

```
python -m pytest tss/lab -q --cov=pricing --cov-branch --cov-fail-under=100
```

Run one suite with branch coverage on the module:

```
python -m pytest tss/lab/tests/test_ep.py -q --cov=pricing --cov-report=term
```

(same form for `test_bva.py`, `test_ceg.py`, `test_mcdc.py`). Coverage is
configured in `pyproject.toml`: `source = ["pricing"]`, `branch = true`.
Current stage: **complete** — 212 tests collected, all green; combined branch
coverage 100 % (57 statements, 22 branches, 0 missed).

## Assignment points 1–7 → artifacts

| Point | Deliverable | Artifacts |
|---|---|---|
| 1 | Program + requirements | `pricing.py` (port of the team's module) + [`SPEC.md`](SPEC.md) |
| 2 | Coverage measurement/comparison | [`docs/coverage-comparison.md`](docs/coverage-comparison.md) |
| 3 | Control-flow graph, V(G), basis paths | [`docs/cfg.drawio`](docs/cfg.drawio) + [`docs/cfg.svg`](docs/cfg.svg) + [`docs/cfg-analysis.md`](docs/cfg-analysis.md) + verifier [`docs/gen_cfg.py`](docs/gen_cfg.py) |
| 4 | Test-design techniques (EP / BVA / CEG / MC-DC) | `tests/test_ep.py` + [`docs/ep.md`](docs/ep.md) · `tests/test_bva.py` + [`docs/bva.md`](docs/bva.md) · `tests/test_ceg.py` + [`docs/ceg.md`](docs/ceg.md) · `tests/test_mcdc.py` + [`docs/mcdc.md`](docs/mcdc.md) |
| 5–6 | Hand-built mutants: killed / surviving / equivalent + demonstration | [`mutants/`](mutants) (3 order-1 mutants + `run_demo.py`) + [`docs/mutants-manual.md`](docs/mutants-manual.md) |
| 7 | Mutation-testing tools, two tools, analysis | [`docs/mutation-analysis.md`](docs/mutation-analysis.md) (mutmut 3.8.0 + cosmic-ray 8.7.0, each × 4 suites) |

(Point labels 2, 3, 5–6, 7 are the docs' own task headers; points 1 and 4 are
the natural completion of that numbering.)

## Task list (internal) → status

| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Project skeleton + port of the module under test | `pricing.py`, `tests/`, `conftest.py`, `pyproject.toml` | done |
| 2 | Black-box requirements specification | `SPEC.md` | done |
| 3 | Equivalence-partitioning suite (partition table + tests) | `tests/test_ep.py` + `docs/ep.md` | done (52 tests) |
| 4 | Boundary-value-analysis suite (boundary table + tests) | `tests/test_bva.py` + `docs/bva.md` | done (129 tests) |
| 5 | Cause–effect graph + decision-table suite | `tests/test_ceg.py` + `docs/ceg.md` | done (17 tests) |
| 6 | MC/DC suite (truth table + tests) | `tests/test_mcdc.py` + `docs/mcdc.md` | done (14 tests) |
| 7 | Full run of all suites green with branch coverage | `python -m pytest tss/lab -q --cov=pricing --cov-branch --cov-fail-under=100` | done (212 passed, 100 %) |
| 8 | CFG + coverage comparison + mutation labs (assignment points 2, 3, 5–7) | `docs/`, `mutants/` | done (see map above) |

## Team contribution declaration (assignment points 1–7)

**FILL IN BEFORE SUBMISSION** — names and final percentages are the team's own
declaration. Per the assignment, each member declares at the end of the
project which of points 1–7 they contributed to, with percentages summing to
100 %.

| Member | Points contributed to | Own percentage |
|---|---|---|
| Member 1 — [NAME] | points 1a, 1c, 2, 3 | [XX] % |
| Member 2 — [NAME] | points 1b, 4, 5, 6, 7 | [YY] % |

[XX] + [YY] = 100 %. If this is a solo submission, keep one row and declare
100 %.

AI assistance for every deliverable is itemized in
[`AI_USAGE.md`](AI_USAGE.md); the declaration above concerns the team's own
direction, review and responsibility, which the members state in person at
the presentation.
