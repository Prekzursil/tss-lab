# Manual mutation testing — tasks 5 & 6 (pricing module)

Hands-on mutation lab on `tss/lab/pricing.py`. Three order-1 mutants were
hand-built as full copies of the module in `tss/lab/mutants/`:

| variant | file | mutated line (in `pricing.py` numbering) | change | operator class | claimed verdict |
|---|---|---|---|---|---|
| equivalent | `mutants/mutant_equivalent.py` | 148 (`compute_totals`, final clamp) | `if total < 0:` → `if total <= 0:` | relational operator replacement (`<` → `<=`) | **EQUIVALENT** — no test can kill it |
| killed | `mutants/mutant_killed.py` | 59 (`compute_fee`, C3) | `if fee_type == "percent":` → `if fee_type != "percent":` | relational operator replacement (`==` → `!=`) | **KILLED** by the chosen test |
| surviving | `mutants/mutant_surviving.py` | 57 (`compute_fee`, C2) | `if fee_value <= 0:` → `if fee_value <= 4:` | boundary (constant) shift `0` → `4` | **SURVIVED** by the chosen test, killed by the full suite |

Order-1 evidence (`diff pricing.py mutants/<m>.py`, run 2026-10-16): each
mutant differs from `pricing.py` on exactly one line —

```
148c148
<     if total < 0:  # pragma: no cover
---
>     if total <= 0:  # pragma: no cover

59c59
<     if fee_type == "percent":
---
>     if fee_type != "percent":

57c57
<     if fee_value <= 0:
---
>     if fee_value <= 4:
```

## 1. Chosen test case

`tests/test_mcdc.py::test_mcdc_c03_compute_fee_type_percent`
(`tss/lab/tests/test_mcdc.py:63-81`) — the MC/DC minimal pair for condition
**C3** `fee_type == "percent"` (`pricing.py:59`). It fixes
`taxable_subtotal=200`, `enabled=True`, `fee_value=5` and flips only
`fee_type`, asserting both rows exactly:

```python
flat    = compute_fee(taxable_subtotal=Decimal("200"), enabled=True, fee_type="flat",    fee_value=Decimal("5"))
percent = compute_fee(taxable_subtotal=Decimal("200"), enabled=True, fee_type="percent", fee_value=Decimal("5"))
assert flat    == Decimal("5.00")   # C3 False -> flat arm
assert percent == Decimal("10.00")  # C3 True  -> 200*5/100
```

## 2. Task 5 — the EQUIVALENT mutant and its proof

**Mutation.** `pricing.py:148`, inside `compute_totals`:

```python
total = taxable + shipping_q + fee + vat      # line 141
...
if total < 0:                                  # line 148  →  mutant: if total <= 0:
    total = Decimal("0.00")                    # line 149
total = quantize_money(total, rounding=rounding)   # line 150
```

**Claim.** On the entire declared input domain of `compute_totals` (finite
`Decimal`/`int` money arguments, `bool` flags, any string `fee_type`, any
string `rounding`, `Decimal | None` `vat_override`), the mutant returns
field-for-field identical `PricingBreakdown`s to the original.

**Proof.** The two programs are byte-identical except for the relational
operator guarding line 149. The mutated variable `total` has exactly one
consumer after the guard: the `quantize_money` at line 150, whose result feeds
the `total` field of the returned record. So the programs can differ only if
the guard change alters the *value* carried into line 150. Exhaustive case
analysis on the value of `total` produced at line 141:

* **`total > 0`.** Neither `total < 0` nor `total <= 0` holds; neither program
  assigns. Identical.
* **`total < 0`.** Both guards hold; both assign `Decimal("0.00")`. Identical.
  (This case is in fact unreachable — see the invariant below — but the
  equivalence does not depend on unreachability: even if it were reachable,
  both programs clamp the same way.)
* **`total == 0`.** The only case where the guards disagree: the original
  skips the assignment, the mutant executes `total = Decimal("0.00")`. The
  assignment is a no-op *in value*: `total` is numerically `0` and
  `Decimal("0.00") == 0`, so the value reaching line 150 is `0` either way,
  and line 150 maps both to the same canonical `quantize_money(0) =
  Decimal("0.00")`. It is a no-op even *in representation*: every summand of
  the line-141 sum is either the literal `Decimal("0.00")` or a
  `quantize_money(...)` result, and quantizing to `MONEY_QUANT =
  Decimal("0.01")` always yields a `Decimal` with exponent exactly −2;
  adding same-exponent decimals preserves exponent −2, so a zero sum **is**
  the very object `Decimal("0.00")` (digits `(0,)`, exponent −2) that the
  mutant assigns. No other field of the returned record reads `total`.

**Invariant (the guard is dead, and `total == 0` is the mutant's only extra
firing point).** Every summand of line 141 is non-negative on every input:

* `taxable` (lines 110–113): floored at `Decimal("0.00")` when the raw
  subtraction goes negative, then quantized ⇒ `taxable ≥ 0`;
* `shipping_q` (lines 114–116): `Decimal("0.00")` when `shipping ≤ 0`, else
  `quantize_money(shipping)` for `shipping > 0` — all four rounding modes
  (half_up / half_even / up / down) resolve only the last kept digit and never
  flip sign ⇒ `shipping_q ≥ 0`;
* `fee` (lines 117–123): `compute_fee(taxable_subtotal=taxable, …)` receives
  the **floored** `taxable ≥ 0`, so it returns `Decimal("0.00")` (disabled or
  `fee_value ≤ 0`), or `quantize_money(taxable·fee_value/100)` with
  `taxable ≥ 0 < fee_value`, or `quantize_money(fee_value)` with
  `fee_value > 0` — all non-negative. (`compute_fee`'s one negativity hazard —
  a percent fee on a negative taxable, cf. EP
  `test_f3_percent_negative_taxable` — is unreachable from `compute_totals`
  precisely because of the floor at line 111.)
* `vat` (lines 124–140): `Decimal("0.00")`, or
  `quantize_money(max(vat_override, 0)) ≥ 0`, or `compute_vat(...)` which
  returns `Decimal("0.00")` (disabled / rate ≤ 0 / base ≤ 0) or the quantized
  product of `base > 0` and `rate > 0` — non-negative.

A sum of non-negatives is non-negative, so `total ≥ 0` always: the original
branch is unreachable (consistent with the `# pragma: no cover` at
`pricing.py:142-148`), the mutant's extra firing point is confined to
`total == 0` (where, by the case analysis, it is a no-op), and when
`total == 0` each summand is individually `0`. ∎

**Domain closure.** Non-finite `Decimal`s raise identically in both programs
*before* line 148 (`Decimal("Infinity").quantize(...)` raises
`InvalidOperation`; NaN comparisons like `discount > 0` raise
`InvalidOperation`), so no exceptional path separates them either.

**Corollary.** No test — in this suite or any conceivable suite — can kill
this mutant; the observed full-suite survival (212 passed, receipt below) is
forced by the proof, not luck. This is exactly why equivalent mutants must be
*proven* away, not merely left on the survivors list.

## 3. Task 6 — killed and surviving (both non-equivalent)

### 3a. `mutant_killed` — killed by the chosen test

`pricing.py:59` negated: `fee_type == "percent"` → `fee_type != "percent"`
(the arms of `compute_fee` are swapped). Run against the chosen test, its
**flat row** already fails:

```
>       assert flat == Decimal("5.00")  # C3 False -> flat arm
E       AssertionError: assert Decimal('10.00') == Decimal('5.00')
```

(mutant: `"flat" != "percent"` is True → percent arm → `quantize(200·5/100) =
10.00` instead of the flat `5.00`; the percent row fails symmetrically with
`5.00 != 10.00`.) **Non-equivalence** is witnessed by that single call:
`compute_fee(taxable_subtotal=200, enabled=True, fee_type="percent",
fee_value=5)` = `10.00` (original) vs `5.00` (mutant). Full suite: 20 failed,
192 passed.

### 3b. `mutant_surviving` — survives the chosen test, dies in the full suite

`pricing.py:57` boundary shift: `fee_value <= 0` → `fee_value <= 4`. The
chosen test is an MC/DC pair for C3, so it **pins `fee_value = 5`** in both
rows; `5 <= 4` is exactly as false as `5 <= 0`, both rows take the identical
path in mutant and original, and both assertions pass → **SURVIVED** by the
chosen test. This is the MC/DC discipline's built-in blind spot: a minimal
pair varies one condition and freezes everything else, so it says nothing
about the frozen inputs' own boundaries.

**Non-equivalence** is witnessed by any `fee_value ∈ (0, 4]`:
`compute_fee(taxable_subtotal=100, enabled=True, fee_type="flat",
fee_value=2)` = `2.00` (original) vs `0.00` (mutant) — executed live by
`run_demo.py` (receipt below). The **full suite kills it** (10 failed, 202
passed), which is the empirical proof of non-equivalence and a reminder that a
single test case is never a sufficient mutation filter. Killers include
`test_mcdc_c02_compute_fee_value_le_zero` (positive row `fee_value = 3` now
`3 <= 4` → early `0.00`), BVA `test_b7/b8_fee_value_zero_boundary_*[0.005]`
and `test_b9_flat_fee_tie_per_mode[...]` (`fee_value 2.345 <= 4`), and
`test_b20_totals_minimal_sum_boundary` (flat `fee_value 0.01`).

## 4. Demonstrating output

`python tss/lab/mutants/run_demo.py` (run 2026-10-16, exit code 0). For each
variant the runner installs the mutant as `pricing.py` in an isolated sandbox
with a copy of `tss/lab/tests/` and runs (a) the chosen test case and (b) the
full 212-test suite via `python -m pytest -q`; it also executes the
distinguishing inputs in-process:

```
==============================================================================
TSS lab tasks 5-6: manual mutation demo  (chosen test case: tests/test_mcdc.py::test_mcdc_c03_compute_fee_type_percent)
==============================================================================
--- distinguishing-input probes (in-process, original vs mutant) ---
[mutant_killed]     compute_fee(taxable=200, enabled=True, percent, 5): original=10.00 mutant=5.00 -> DIFFER (non-equivalent)
[mutant_surviving]  compute_fee(taxable=100, enabled=True, flat, 2):    original=2.00 mutant=0.00 -> DIFFER (non-equivalent)
[mutant_equivalent] compute_totals all-zero (total==0, mutated branch FIRES)  -> all 7 fields IDENTICAL
[mutant_equivalent] compute_totals negative subtotal (total==0, fires)        -> all 7 fields IDENTICAL
[mutant_equivalent] compute_totals normal positive (total>0)                  -> all 7 fields IDENTICAL
[mutant_equivalent] compute_totals full scenario (total 203.50)               -> all 7 fields IDENTICAL

=== mutant_equivalent ===
  chosen test : SURVIVED  (1 passed in 1.90s)
  full suite  : SURVIVED  (212 passed in 1.95s)
  VERDICT mutant_equivalent: EQUIVALENT
  claim check (chosen-test): expected SURVIVED -> MATCH
  claim check (full-suite): expected SURVIVED -> MATCH
  claim check (verdict): expected EQUIVALENT -> MATCH

=== mutant_killed ===
  chosen test : KILLED    (1 failed in 1.62s | FAILED tests/test_mcdc.py::test_mcdc_c03_compute_fee_type_percent - Assertion...)
  full suite  : KILLED    (20 failed, 192 passed in 2.83s | FAILED tests/test_bva.py::test_b10_percent_fee_tie_per_mode[half_up-2.35] - A...; FAILED tests/test_bva.py::test_b10_percent_fee_tie_per_mode[half_even-2.34]; FAILED tests/test_bva.py::test_b10_percent_fee_tie_per_mode[up-2.35] - Assert...)
  VERDICT mutant_killed: KILLED
  claim check (chosen-test): expected KILLED -> MATCH
  claim check (full-suite): expected KILLED -> MATCH
  claim check (verdict): expected KILLED -> MATCH

=== mutant_surviving ===
  chosen test : SURVIVED  (1 passed in 1.00s)
  full suite  : KILLED    (10 failed, 202 passed in 3.66s | FAILED tests/test_bva.py::test_b7_fee_value_zero_boundary_flat[0.005] - Asser...; FAILED tests/test_bva.py::test_b8_fee_value_zero_boundary_percent[0.005] - As...; FAILED tests/test_bva.py::test_b9_flat_fee_tie_per_mode[half_up-2.35] - Asser...)
  VERDICT mutant_surviving: SURVIVED
  claim check (chosen-test): expected SURVIVED -> MATCH
  claim check (full-suite): expected KILLED -> MATCH
  claim check (verdict): expected SURVIVED -> MATCH

==============================================================================
DEMO RESULT: ALL CLAIMS MATCH (kill / survive / equivalence demonstrated)
==============================================================================
```

Verdict semantics: KILLED/SURVIVED are decided per test scope (chosen test
case vs full suite); EQUIVALENT is decided by the §2 proof plus survival of
both scopes and the `total == 0` firing-state probes.

## 5. Reproducing

```
cd <repo root>
python -m pytest tss/lab/tests -q                 # baseline: 212 passed
python tss/lab/mutants/run_demo.py                # this demo; exit 0 iff all claims match
for m in mutant_equivalent mutant_killed mutant_surviving; do
    diff tss/lab/pricing.py tss/lab/mutants/$m.py   # exactly one line differs each
done
```

Baseline receipt (original module, before any mutation):
`python -m pytest "C:/Users/Prekzursil/.zcode/workspace/default/tss/lab/tests" -q`
→ `212 passed in 1.62s` (pytest 8.4.2).
