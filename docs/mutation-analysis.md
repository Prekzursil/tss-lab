# Mutation analysis: two tools × four suites on `pricing`

Task 7 of the TSS lab. The four black-box suites (EP, BVA, CEG, MC/DC —
tasks 1–4 test-design sets) were each run **separately** against machine-generated
mutants of `tss/lab/pricing.py`, with **two** mutation-testing tools:

- **mutmut 3.8.0** — pre-installed on Windows, but mutmut 3.x refuses to run
  natively on Windows (`mutmut --version` → *"To run mutmut on Windows, please
  use the WSL. Native windows support is tracked in issue
  boxed/mutmut#397"* — it relies on `os.fork()`). Per the tool's own guidance the
  same pinned version was installed and run inside WSL Ubuntu (Python 3.12.3,
  fresh venv `~/venv-mutmut`).
- **cosmic-ray 8.7.0** — installed as the second tool on the ambient Windows
  Python 3.14.6 (`pip install cosmic-ray` → *Successfully installed …
  cosmic-ray-8.7.0*; `cosmic-ray --version` → *cosmic-ray, version 8.7.0*).
  cosmic-ray was the first tool tried per the task order and it installed
  cleanly, so mutatest/poodle were not attempted.

Score convention throughout: **mutation score = killed / (killed + survived)**.
Neither tool produced any timeout / suspicious / skipped / incompetent outcomes
in any run (mutmut's live counter showed `⏰ 0 🤔 0 🔇 0 🫥 0` and cosmic-ray's
dump only `killed`/`survived`), so the denominator is simply the total mutant
count for each tool.

## Measurement protocol

Both tools ran on **copies** — `tss/lab/pricing.py` itself is untouched
(verified: md5 `6d716bcc5d258808c8b2ec98aaf550d9` before and after every run).

**mutmut 3.8.0** (WSL, scratch tree `~/mutmut-lab/<suite>/` per suite):
`pricing.py` + only that suite's test file + a `setup.cfg`:

```ini
[mutmut]
source_paths=pricing.py
pytest_add_cli_args_test_selection=tests/test_<suite>.py
```

Run per suite (bounded by `timeout 560`):

```
cd ~/mutmut-lab/<suite> && timeout 560 ~/venv-mutmut/bin/mutmut run
~/venv-mutmut/bin/mutmut results --all true | awk '{print $NF}' | sort | uniq -c
```

One deviation from the lab files, in the scratch copies only: `tests/conftest.py`
uses `sys.path.append(LAB_ROOT)` instead of `sys.path.insert(0, …)`, so that
mutmut's generated `mutants/` directory stays first on `sys.path` and the tests
import the trampoline module (mutmut 3.8 detects and aborts on conftest
sys.path-injection that shadows the mutants tree — `__main__.py:858`). Test
behavior is unchanged (the appended original root is never reached first).
Wall time per suite: 11–25 s (7.1–16.3 mutations/second), all four suites
completed well inside the bound.

**cosmic-ray 8.7.0** (Windows, scratch tree `%TEMP%\tss-mutation\cr-<suite>\`
per suite): `pricing.py` + original `conftest.py` + only that suite's test
file + `cr.toml`:

```toml
[cosmic-ray]
module-path = "pricing.py"
timeout = 60.0
excluded-modules = []
test-command = "python -m pytest tests/test_<suite>.py -x -q"

[cosmic-ray.distributor]
name = "local"
```

Run per suite (the four execs were launched in parallel as detached processes
and finished in ~11.5 min total, `ALLDONE 2026-10-16T23:41:29`):

```
cosmic-ray init cr.toml session.sqlite        # enumerates 226 pending mutations
cosmic-ray exec cr.toml session.sqlite        # applies/runs/restores per mutant
cosmic-ray dump session.sqlite                # JSON-lines of [workitem, result]
```

After the runs every scratch `pricing.py` was again md5-identical to the
original (cosmic-ray restores the file after each mutant).

Clean-suite sanity per scratch dir (before any mutation): EP 52 passed,
BVA 129 passed, CEG 17 passed, MC/DC 14 passed.

## Results

| Tool | Suite | Killed | Survived | Total | Score |
|------|-------|-------:|---------:|------:|------:|
| mutmut 3.8.0 | EP | 133 | 43 | 176 | **75.57 %** |
| mutmut 3.8.0 | BVA | 137 | 39 | 176 | **77.84 %** |
| mutmut 3.8.0 | CEG | 117 | 59 | 176 | **66.48 %** |
| mutmut 3.8.0 | MC/DC | 108 | 68 | 176 | **61.36 %** |
| cosmic-ray 8.7.0 | EP | 186 | 40 | 226 | **82.30 %** |
| cosmic-ray 8.7.0 | BVA | 199 | 27 | 226 | **88.05 %** |
| cosmic-ray 8.7.0 | CEG | 183 | 43 | 226 | **80.97 %** |
| cosmic-ray 8.7.0 | MC/DC | 184 | 42 | 226 | **81.42 %** |

mutmut generates **176** mutants on `pricing.py`, cosmic-ray **226** (50 more).
Survivors by function (both tools agree on the hot spots):

| Suite | mutmut survivors (quantize/fee/vat/totals) | cosmic-ray survivors |
|-------|--------------------------------------------|----------------------|
| EP    | 2 / 6 / 6 / 29                             | 1 / 6 / 6 / 27      |
| BVA   | 2 / 3 / 8 / 26                             | 1 / 3 / 4 / 18 (+1 module-level) |
| CEG   | 10 / 8 / 10 / 31                           | 1 / 6 / 8 / 27 (+1 module-level) |
| MC/DC | 10 / 8 / 8 / 42                            | 1 / 6 / 6 / 28 (+1 module-level) |

## Why the suites score differently

The two tools agree on the head of the ranking and diverge at the tail:

- **BVA is the best suite under both tools** (77.84 % / 88.05 %). Its 129
  boundary-anchored tests pin exact values on both sides of every decision
  boundary, which is precisely what kills comparison-operator mutants
  (`<=` ↔ `<`, `>` ↔ `>=` …) and boundary-value arithmetic swaps.
- **EP is second under both tools** (75.57 % / 82.30 %). Its 52 partition tests
  additionally pin the *rounding-mode* partition (all four `rounding` values)
  and the fee-type partition, which is why only 2 of mutmut's string mutants on
  the `"half_up"` default survive (CEG/MC/DC leave 10 alive each — see below).
  EP is also the only suite that kills cosmic-ray's module-level
  `frozen=True → frozen=False` mutant (`core/ReplaceTrueWithFalse`,
  pricing.py:36): only EP verifies the breakdown's immutability.
- **CEG and MC/DC trail under both tools**, and their order flips: mutmut says
  CEG (66.48 %) > MC/DC (61.36 %); cosmic-ray says MC/DC (81.42 %) ≳ CEG
  (80.97 %) — near-tie. The reason for the flip is operator coverage, not test
  quality: MC/DC's 14 minimal-pair tests leave 42 mutmut survivors in
  `compute_totals` alone (vs CEG's 31) because mutmut's hard mutants there are
  *default-value and string mutations on knobs the pair holds neutral* (e.g.
  `"half_up"` → `"XXhalf_upXX"`, `rounding` default flips) — a minimal pair
  deliberately fixes the other conditions, so mutants that only misbehave
  under a non-neutral setting are unobservable. cosmic-ray cannot generate
  string/default mutants at all, so that whole gap vanishes from its 226 and
  the two suites land within half a point of each other.
- **Absolute scores are ~5–20 points higher under cosmic-ray for every suite.**
  Two mechanical reasons: (a) cosmic-ray's extra mutants are mostly *gross*
  operator swaps that any test kills (e.g. `* → <<`, `* → **`, `== → is` on
  `fee_type`), inflating the denominator with easy kills; (b) 11 of
  cosmic-ray's 226 are `BitOr → *` mutations of the **type annotation**
  `Decimal | None` (pricing.py:104) — runtime no-ops under
  `from __future__ import annotations` that survive in *every* suite and cost
  each score ~5 points of headroom by themselves.

## Mutation operators: what each tool actually has

**cosmic-ray 8.7.0** ships **213 named operator plugins** (receipt:
`python -c "import cosmic_ray.plugins as p; print(len(p.operator_names()))"`
→ 213, all `core/*`). On `pricing.py`, **83 distinct operators fired,
producing 226 mutants** (from the session dump's `operator_name` fields).
Concrete named operators in this run, with counts:

| cosmic-ray operator (named in dump output) | Mutants | Note |
|---|---:|---|
| `core/NumberReplacer` | 16 | numeric literal → n+1 and n−1 (source: `operators/number_replacer.py`, `OFFSETS = [+1, -1]`) |
| `core/AddNot` | 14 | insert `not` before expressions |
| `core/ReplaceBinaryOperator_Mul_Add` … `_Mul_Sub` (11 targets per site, 6 sites) | 66 | **full cross-product**: every binary op → every other binary op |
| `core/ReplaceBinaryOperator_Add_*` (33), `_Div_*` (22), `_Sub_*` (11), `_BitOr_*` (11) | 77 | includes the 11 annotation-union no-ops |
| `core/ReplaceComparisonOperator_*` (`LtE_Eq/Gt/GtE/Lt/NotEq`, `Lt_*`, `Gt_*`, `Eq_*` incl. `Eq_Is`/`Eq_IsNot`, `IsNot_Is`) | 48 | comparison cross-product incl. `is`/`is not` targets |
| `core/ReplaceUnaryOperator_Delete_Not` | 3 | replaces `del` with `not` (fires on `not` nodes as a *replacement*, not a removal) |
| `core/RemoveDecorator` | 1 | `@dataclass(frozen=True)` — killed by all suites |
| `core/ReplaceTrueWithFalse` | 1 | `frozen=True` → `frozen=False` — killed only by EP (the other three suites' scores would each gain ~0.44 pts if they asserted immutability) |

Operators present in cosmic-ray's catalogue but with **zero** hits on this
module: `core/ReplaceAndWithOr` / `core/ReplaceOrWithAnd` (no boolean operators
in `pricing.py` — conditions are separate `if`s), `core/ExceptionReplacer`,
`core/VariableInserter`, `core/VariableReplacer`, `core/ZeroIterationForLoop`,
`core/ReplaceBreakWithContinue` / `core/ReplaceContinueWithBreak` (no loops),
`core/ReplaceFalseWithTrue` (no `False` literal).

**mutmut 3.8.0** does not name its operators in output (mutant IDs like
`pricing.x_compute_fee__mutmut_10` + a diff from `mutmut show`); its operator
set is the mutator table in `mutmut/mutation/mutators.py` (receipts below):

| mutmut operator (function in `mutators.py`) | Behavior | Verified example from this run |
|---|---|---|
| `operator_number` | n → n+1 (only; no n−1) | — (few bare numbers in module) |
| `operator_string` | `"s"` → `"XXsXX"`, `"s"`→lower, →upper | `"half_up"` → `"XXhalf_upXX"`; `"percent"` → `"XXpercentXX"` / `"PERCENT"` (survived/killed per suite) |
| `operator_swap_op` (`_operator_mapping`) | **one** target per source op: `+`→`-`, `*`→`/`, `//`→`/`, `%`→`/`, `**`→`*`, `&`→`\|`, `^`→`&`, `<<`→`>>`, `<`→`<=`, `>`→`>=`, `==`→`!=`, `and`↔`or`, aug-assign variants | `if fee_type == "percent":` → `!=` (killed) |
| `operator_remove_unary_ops` | **removes** `not` / `~` entirely | `if not enabled:` → `if enabled:` (killed) |
| `operator_name` | `True`↔`False`, `deepcopy`→`copy` | — |
| `_keyword_mapping` | `is`↔`is not`, `in`↔`not in`, `break`→`return`, `continue`→`break` | — |
| `operator_assignment` | `a = b` → `a = None` | — |
| `operator_augmented_assignment` | `a += b` → `a = b` | — |
| `operator_arg_removal` / `operator_dict_arguments` | remove call arguments / kwargs→dict | — |
| `operator_symmetric/unsymmetric_string_methods_swap` | `str.upper`↔`str.lower` etc. | — |
| `operator_lambda`, `operator_match`, `operator_if_exp` | lambda→None; drop match cases; neutralize ternary condition | — |

### Concrete operator differences, and how they show in the scores

1. **Cross-product vs single-target operator swaps.** For the six `*` sites
   cosmic-ray generates 11 mutants each (`Mul→Add, BitAnd, BitOr, BitXor, Div,
   FloorDiv, LShift, Mod, Pow, RShift, Sub` — 66 mutants); mutmut generates one
   (`* → /`, 6 mutants). Same for comparisons: `<=` (3 sites) → 15 cosmic-ray
   mutants vs 3 mutmut mutants (`<=` → `<` only). This is the bulk of
   226-vs-176. Score effect: the exotic targets (`* → <<`, `== → is`) change
   behavior grossly, so *every* suite kills them — this alone lifts every
   cosmic-ray score over its mutmut counterpart (it accounts for most of the
   +6.7-point EP gap; the larger CEG/MC/DC gaps of +14.5/+20.1 additionally
   reflect mutmut's string mutants that cosmic-ray cannot make — see #2).
2. **String literals: mutmut yes, cosmic-ray no.** `operator_string` mutates
   `"half_up"` (default arg), `"percent"`, `"0.01"`, `"100"` …; cosmic-ray has
   no string operator at all (its `NumberReplacer` only sees bare numerals —
   every money constant in this module hides inside `Decimal("…")` strings).
   Score effect: the largest single block of *real* (non-equivalent) survivors
   under mutmut — 10 in `quantize_money` for CEG and MC/DC each vs 2 for EP/BVA
   — is invisible to cosmic-ray, which sees only 1 quantize survivor per suite
   (the `MONEY_QUANT`-adjacent `*`→`/` mutant). This is exactly why
   mutmut separates the suites much more sharply (75.6 vs 61.4) than
   cosmic-ray does (82.3 vs 81.4).
3. **Number mutation: ±1 vs +1, and zero-adjacent equivalence.** cosmic-ray's
   `NumberReplacer` fires 16 times — twice per `0` literal in the eight
   `<= 0` / `> 0` / `< 0` guards (n+1 and n−1) — and **all 16 survive in all
   four suites**: `fee_value <= 0 → <= 1` only differs for sub-unit positive
   fees (e.g. `Decimal("0.50")`) that no suite probes, and the `→ -1` variants
   are semantically equivalent for money (both branches yield `0.00`). mutmut's
   `operator_number` (n+1 only) has nothing to fire on here. These 16 are
   ~40 % of cosmic-ray's survivor count in every suite.
4. **Unary `not`: removal vs replacement.** mutmut's
   `operator_remove_unary_ops` turns `if not enabled:` into `if enabled:`
   (verified diff) — a control-flow inversion every suite kills. cosmic-ray's
   unary operators *replace* one unary op with another
   (`core/ReplaceUnaryOperator_Delete_Not` etc.); it has no "delete the not"
   operator, so this whole mutant family is mutmut-only.
5. **Module scope.** cosmic-ray mutated module-level code
   (`@dataclass(frozen=True)`): `core/RemoveDecorator` (killed everywhere —
   removing `@dataclass` breaks construction) and
   `core/ReplaceTrueWithFalse` → `frozen=False` (killed **only by EP**, the
   sole suite asserting immutability). mutmut's trampoline architecture
   mutates function bodies only (all 176 mutant IDs are
   `pricing.x_<function>__mutmut_N`; `mutmut results --all true` lists no
   module-level mutants), so it cannot see `frozen=True` at all.
6. **Equivalent-mutant noise from annotations.** 11 of cosmic-ray's survivors
   are `BitOr → X` on the `Decimal | None` annotation union — dead code at
   runtime under postponed annotation evaluation, surviving in every suite and
   capping all cosmic-ray scores at ≤ 95.1 % regardless of test quality. mutmut
   (LibCST-based) produces no annotation-operator mutants of this kind.

## Environment & receipts

- Windows 10 (win32), Python 3.14.6, pip 26.2.1, pytest 8.4.2.
  `pip install cosmic-ray` → `Successfully installed … cosmic-ray-8.7.0 …`;
  `cosmic-ray --version` → `cosmic-ray, version 8.7.0`.
- WSL Ubuntu (wsl2): Python 3.12.3, venv `~/venv-mutmut`,
  `pip show mutmut` → `Version: 3.8.0`.
- mutmut per suite (EP receipt, final line of `mutmut run`):
  `⠏ 176/176 🎉 133 🫥 0 ⏰ 0 🤔 0 🙁 43 🔇 0 🧙 0` + `16.32 mutations/second`
  (BVA 15.03, CEG 7.14, MC/DC 13.79 mutations/second; all `timeout 560`,
  none hit the bound). Tallies via `mutmut results --all true`.
- cosmic-ray per suite: `init` reported 226 pending items in each of the four
  sessions; `exec` (4× parallel, detached) → `ALLDONE 2026-10-16T23:41:29`;
  dump tallies `{'killed': 186, 'survived': 40}` (EP) etc. as in the table;
  post-run md5 of every scratch `pricing.py` = `6d716bcc…550d9` (restored).
- Operator receipts: `cosmic_ray.plugins.operator_names()` (213 names);
  `operator_name` histogram from `cr-ep/dump-done.jsonl` (83 distinct, 226
  items); `cosmic_ray/operators/number_replacer.py` (`OFFSETS = [+1, -1]`);
  `mutmut/mutation/mutators.py` tables; `mutmut show pricing.x_compute_fee__mutmut_10`
  (`==` → `!=`), `__mutmut_11/12` (`"percent"` → `"XXpercentXX"` / `"PERCENT"`),
  `pricing.x_quantize_money__mutmut_1` (`"half_up"` → `"XXhalf_upXX"`),
  `pricing.x_compute_fee__mutmut_3` (`if not enabled:` → `if enabled:`).
- Scratch trees (kept for re-inspection): WSL `~/mutmut-lab/{ep,bva,ceg,mcdc}`,
  Windows `%TEMP%\tss-mutation\cr-{ep,bva,ceg,mcdc}` (+ `cr_tally.py`,
  `run-cr-all.ps1`, `cr-all.log`). Nothing under `tss/lab` was modified.
