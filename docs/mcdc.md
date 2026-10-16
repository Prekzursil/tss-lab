# MC/DC derivation — `tss/lab/pricing.py`

Technique: **Modified Condition/Decision Coverage**. For every condition `C`
in every decision `D` of the module, exhibit a *pair* of executions in which

1. `C` evaluates to different outcomes (T/F),
2. every other condition that feeds the same decision holds the same outcome,
3. the decision's outcome (and hence an observable output) changes.

Sources read for this derivation: `tss/lab/SPEC.md` (§9 MC/DC anchor) and
`tss/lab/pricing.py` (line numbers cited below refer to that file, read
2026-10-16). The module is frozen; all expected values below were hand-derived
from the code paths and asserted as exact `Decimal`s in
`tss/lab/tests/test_mcdc.py`.

`quantize_money` contains **no conditions** (the rounding-mode fallback at
pricing.py:32 is a branch-free `dict.get`), and `PricingBreakdown` is a plain
frozen dataclass — so the inventory below is the complete set of module
conditions.

---

## 1. Condition inventory

| ID  | Condition (as written)      | Location    | Decision it feeds                                   | Function        |
|-----|-----------------------------|-------------|-----------------------------------------------------|-----------------|
| C1  | `not enabled`               | pricing.py:55  | fee early-return #1 (fee = 0.00)                 | `compute_fee`   |
| C2  | `fee_value <= 0`            | pricing.py:57  | fee early-return #2 (fee = 0.00)                 | `compute_fee`   |
| C3  | `fee_type == "percent"`     | pricing.py:59  | percent vs flat computation                      | `compute_fee`   |
| C4  | `not enabled`               | pricing.py:77  | VAT early-return #1 (vat = 0.00)                | `compute_vat`   |
| C5  | `vat_rate_percent <= 0`     | pricing.py:79  | VAT early-return #2 (vat = 0.00)                | `compute_vat`   |
| C6  | `apply_to_shipping`         | pricing.py:82  | add shipping to VAT base                        | `compute_vat`   |
| C7  | `apply_to_fee`              | pricing.py:84  | add fee to VAT base                              | `compute_vat`   |
| C8  | `base <= 0`                 | pricing.py:86  | VAT early-return #3 (vat = 0.00)                | `compute_vat`   |
| C9  | `discount > 0`              | pricing.py:108 | discount contribution ternary (T2)              | `compute_totals`|
| C10 | `taxable < 0`               | pricing.py:111 | taxable floor-at-zero guard (T3)                 | `compute_totals`|
| C11 | `shipping > 0`              | pricing.py:115 | shipping contribution ternary (T4)               | `compute_totals`|
| C12 | `not vat_enabled`           | pricing.py:124 | 3-way VAT selector, arm 1 (T6)                   | `compute_totals`|
| C13 | `vat_override is not None`  | pricing.py:126 | 3-way VAT selector, arm 2 (T6)                   | `compute_totals`|
| C14 | `vat_override > 0`          | pricing.py:128 | override clamp ternary inside arm 2              | `compute_totals`|
| C15 | `total < 0`                 | pricing.py:148 | defensive total floor                             | `compute_totals`|

C1–C14 are each exercised by one minimal MC/DC pair (14 pairs → 14 tests).
C15 is **unreachable** — see §4.

Guards that appear in both `compute_fee` and `compute_vat` (C1/C4, C2/C5) are
distinct conditions feeding distinct decisions and get distinct pairs.

---

## 2. Truth tables and chosen pairs

For the single-condition decisions (all of the module's `if`s except the T6
selector), "all other conditions fixed" is realized by fixing every *upstream*
guard that could mask the outcome (e.g. to expose C2 the pair keeps
`enabled=True`; to expose C8 it keeps `enabled=True` and `rate>0`).

### C1 — `not enabled` in `compute_fee` (pricing.py:55)

Held fixed: `fee_type="flat"`, `fee_value=3`, `taxable_subtotal=100`.

| Row | enabled | C1    | Decision (branch)      | Observable fee |
|-----|---------|-------|------------------------|----------------|
| a   | `False` | **T** | early return           | `0.00`         |
| b   | `True`  | **F** | fall through to C2/C3  | `3.00`         |

**Pair P1 = (a, b).**

### C2 — `fee_value <= 0` in `compute_fee` (pricing.py:57)

Held fixed: `enabled=True` (C1=F so it cannot mask), `fee_type="flat"`,
`taxable_subtotal=100`.

| Row | fee_value | C2    | Decision (branch)     | Observable fee |
|-----|-----------|-------|-----------------------|----------------|
| a   | `-3`      | **T** | early return          | `0.00`         |
| b   | `3`       | **F** | compute flat fee      | `3.00`         |

**Pair P2 = (a, b).**

### C3 — `fee_type == "percent"` in `compute_fee` (pricing.py:59)

Held fixed: `enabled=True`, `fee_value=5`, `taxable_subtotal=200` (values
chosen so the two arms give clearly different amounts).

| Row | fee_type    | C3    | Decision (branch)   | Observable fee                     |
|-----|-------------|-------|---------------------|------------------------------------|
| a   | `"percent"` | **T** | percent arm         | `200·5/100 = 10.00`                |
| b   | `"flat"`    | **F** | flat arm            | `5.00`                             |

**Pair P3 = (a, b).** (C3 is a module condition beyond the enumerated list in
the task statement but is required by "every condition in the module".)

### C4 — `not enabled` in `compute_vat` (pricing.py:77)

Held fixed: `taxable_subtotal=100`, `shipping=10`, `fee=5`, `vat_rate_percent=10`,
`apply_to_shipping=True`, `apply_to_fee=True`.

| Row | enabled | C4    | Decision (branch)     | Observable vat |
|-----|---------|-------|-----------------------|----------------|
| a   | `False` | **T** | early return          | `0.00`         |
| b   | `True`  | **F** | fall through          | base 115 → `11.50` |

**Pair P4 = (a, b).**

### C5 — `vat_rate_percent <= 0` in `compute_vat` (pricing.py:79)

Held fixed: `enabled=True`, `taxable_subtotal=100`, `shipping=0`, `fee=0`,
apply flags `False` (C6=C7=F, cannot mask).

| Row | vat_rate_percent | C5    | Decision (branch)    | Observable vat |
|-----|------------------|-------|----------------------|----------------|
| a   | `-10`            | **T** | early return         | `0.00`         |
| b   | `10`             | **F** | compute VAT          | `10.00`        |

**Pair P5 = (a, b).**

### C6 — `apply_to_shipping` in `compute_vat` (pricing.py:82)

Held fixed: `enabled=True`, `rate=10`, `taxable_subtotal=100`, `shipping=10`,
`fee=0`, `apply_to_fee=False`. Base stays > 0 in both rows so C8 cannot mask.

| Row | apply_to_shipping | C6    | Decision (branch)          | Observable vat |
|-----|-------------------|-------|----------------------------|----------------|
| a   | `False`           | **F** | skip `base += shipping`    | base 100 → `10.00` |
| b   | `True`            | **T** | add shipping               | base 110 → `11.00` |

**Pair P6 = (a, b).**

### C7 — `apply_to_fee` in `compute_vat` (pricing.py:84)

Held fixed: `enabled=True`, `rate=10`, `taxable_subtotal=100`, `shipping=0`,
`fee=8`, `apply_to_shipping=False`.

| Row | apply_to_fee | C7    | Decision (branch)      | Observable vat   |
|-----|--------------|-------|------------------------|------------------|
| a   | `False`      | **F** | skip `base += fee`     | base 100 → `10.00` |
| b   | `True`       | **T** | add fee                | base 108 → `10.80` |

**Pair P7 = (a, b).**

### C8 — `base <= 0` in `compute_vat` (pricing.py:86)

Held fixed: `enabled=True`, `rate=10`, apply flags `False`, `shipping=0`,
`fee=0`. The decision's sole operand is `base`, here driven through
`taxable_subtotal`.

| Row | taxable_subtotal | base | C8    | Decision (branch)   | Observable vat |
|-----|------------------|------|-------|---------------------|----------------|
| a   | `-40`            | −40  | **T** | early return        | `0.00`         |
| b   | `40`             | +40  | **F** | compute VAT         | `4.00`         |

**Pair P8 = (a, b).** (Interior values −40/+40 chosen deliberately; the
`base = 0` crossing itself belongs to the BVA suite.)

### C9 — `discount > 0` in `compute_totals` (pricing.py:108)

Held fixed: `subtotal=100`, `shipping=0`, `fee_enabled=False`,
`vat_enabled=False` (so fee/VAT cannot mask the reported fields).

| Row | discount | C9    | Decision (branch) of the ternary      | discount reported | taxable    | total    |
|-----|----------|-------|---------------------------------------|-------------------|------------|----------|
| a   | `-2`     | **F** | `Decimal("0.00")`                     | `0.00`            | `100.00`   | `100.00` |
| b   | `5`      | **T** | `quantize_money(discount)`            | `5.00`            | `95.00`    | `95.00`  |

**Pair P9 = (a, b).**

### C10 — `taxable < 0` in `compute_totals` (pricing.py:111)

Held fixed: `subtotal=100`, `shipping=0`, fee/VAT disabled, and `discount>0`
**True in both rows** (C9 fixed) — only the resulting taxable crosses zero.

| Row | discount | taxable (raw) | C10   | Decision (branch)        | taxable reported | total    |
|-----|----------|---------------|-------|--------------------------|------------------|----------|
| a   | `120`    | −20.00        | **T** | floor at `0.00`          | `0.00`           | `0.00`   |
| b   | `80`     | +20.00        | **F** | keep                     | `20.00`          | `20.00`  |

**Pair P10 = (a, b).**

### C11 — `shipping > 0` in `compute_totals` (pricing.py:115)

Held fixed: `subtotal=100`, `discount=0`, fee/VAT disabled.

| Row | shipping | C11   | Decision (branch) of the ternary | shipping reported | total    |
|-----|----------|-------|----------------------------------|-------------------|----------|
| a   | `-3`     | **F** | `Decimal("0.00")`                | `0.00`            | `100.00` |
| b   | `7`      | **T** | `quantize_money(shipping)`       | `7.00`            | `107.00` |

**Pair P11 = (a, b).**

### C12/C13 — the 3-way VAT selector in `compute_totals` (pricing.py:124-126)

Compound decision (SPEC T6): arm 1 `not vat_enabled` → vat `0.00`; arm 2
`vat_override is not None` → clamp(override); arm 3 `else` → `compute_vat`.
Let **E** = `vat_enabled`, **O** = (`vat_override is not None`).

Full truth table:

| E     | O            | C12 `not E` | C13 `O` | Arm executed | vat source        | Row used |
|-------|--------------|-------------|---------|--------------|-------------------|----------|
| `F`   | absent       | **T**       | **F**   | 1            | `0.00`            | P12-a    |
| `F`   | present      | **T**       | **T**   | 1            | `0.00` (override masked) | not needed for MC/DC (CEG material) |
| `T`   | absent       | **F**       | **F**   | 3            | `compute_vat`     | P12-b / P13-a |
| `T`   | present      | **F**       | **T**   | 2            | clamp(override)   | P13-b   |

Common fixed inputs for both pairs: `subtotal=100`, `discount=0`, `shipping=0`,
`fee_enabled=False`, `vat_rate_percent=10`, apply flags `False` → the arm-3
computation is `100 · 10/100 = 10.00`.

| Pair | Rows vary in        | Fixed                                           | vat outcomes       |
|------|---------------------|--------------------------------------------------|--------------------|
| P12  | `vat_enabled` F→T   | `vat_override=None` (O=F both rows)              | `0.00` → `10.00`   |
| P13  | override None→`3`   | `vat_enabled=True` (C12=F both rows)             | `10.00` → `3.00`   |

P12 shows C12 independently picks arm 1 vs arm 3; P13 shows C13 independently
picks arm 3 vs arm 2 (with C12 held False, the only context in which C13 is
not masked). Row (F, present) — override masked by disabled VAT — documents
the masking but is not required by MC/DC and is left to the CEG suite.

### C14 — `vat_override > 0` clamp ternary inside arm 2 (pricing.py:128)

Held fixed: `vat_enabled=True` and override present (C12=F, C13=T in both
rows); `subtotal=100`, fee/shipping/discount neutral, rate irrelevant (arm 2
ignores it).

| Row | vat_override | C14   | Ternary result          | vat     | total    |
|-----|--------------|-------|-------------------------|---------|----------|
| a   | `-4`         | **F** | `Decimal("0.00")`       | `0.00`  | `100.00` |
| b   | `4`          | **T** | the override itself    | `4.00`  | `104.00` |

**Pair P14 = (a, b).**

---

## 3. Pair → test mapping

| Pair | Condition | Test function                              |
|------|-----------|--------------------------------------------|
| P1   | C1        | `test_mcdc_c01_compute_fee_not_enabled`    |
| P2   | C2        | `test_mcdc_c02_compute_fee_value_le_zero`  |
| P3   | C3        | `test_mcdc_c03_compute_fee_type_percent`   |
| P4   | C4        | `test_mcdc_c04_compute_vat_not_enabled`    |
| P5   | C5        | `test_mcdc_c05_compute_vat_rate_le_zero`   |
| P6   | C6        | `test_mcdc_c06_compute_vat_apply_shipping` |
| P7   | C7        | `test_mcdc_c07_compute_vat_apply_fee`      |
| P8   | C8        | `test_mcdc_c08_compute_vat_base_le_zero`   |
| P9   | C9        | `test_mcdc_c09_totals_discount_positive`   |
| P10  | C10       | `test_mcdc_c10_totals_taxable_negative`    |
| P11  | C11       | `test_mcdc_c11_totals_shipping_positive`   |
| P12  | C12       | `test_mcdc_c12_totals_vat_not_enabled`     |
| P13  | C13       | `test_mcdc_c13_totals_override_not_none`   |
| P14  | C14       | `test_mcdc_c14_totals_override_positive`   |

Each test executes **both** rows of its pair and asserts the exact `Decimal`
outcome(s) of every field that the decision drives, so the independence
property (same fixed context, one flipped condition, flipped outcome) is
checked, not assumed. Tests are independent: no shared fixtures or state.

Non-duplication note: representatives are deliberately *interior* partition
values (e.g. `discount ∈ {-2, 5}`, `shipping ∈ {-3, 7}`, `base` via
`taxable ∈ {-40, 40}`) rather than boundary values (`0`, `x.xx5` ties), which
belong to the BVA suite; whole-decision truth-table behavior (masking,
impossible combinations) belongs to the CEG suite. This suite covers only the
minimal independence pairs.

---

## 4. C15 — `total < 0` (pricing.py:148): unreachable, no pair exists

The guard is annotated `# pragma: no cover` in the module and a construction
argument (comment at pricing.py:142-147) shows it cannot fire: every summand
of `total = taxable + shipping_q + fee + vat` (pricing.py:141) is
individually non-negative before the sum —

- `taxable` is floored at `0.00` by C10 (pricing.py:111-112);
- `shipping_q` is `0.00` or a quantized positive (C11, pricing.py:114-116);
- `fee` comes from `compute_fee` with `taxable ≥ 0`: it is `0.00` or
  `quantize` of a positive value (pricing.py:57-63) — quantization of a
  positive under any mode never yields a negative;
- `vat` is `0.00`, a quantized `max(0, override)`, or a `compute_vat` result
  which is `0.00` or a quantized positive product (pricing.py:124-140,
  86-88).

Hence `total ≥ 0` on every reachable input, condition C15 cannot be made
true, and no truth-table row with C15 = T exists. This is reported as a fact
of the module, not covered by any test (faking a pair here would be
dishonest); the code is frozen so the guard cannot be removed.

---

## 5. Run receipt

Command (from the workspace root):

```
python -m pytest tss/lab/tests/test_mcdc.py -q
```

Expected/actual: 14 passed, exit 0 (see `receipts` in the submitted result for
the exact output lines).
