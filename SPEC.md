# SPEC.md — Pricing module black-box requirements specification

Status: **requirements baseline v1** (2026-10-16). This document specifies the
*observable* behavior of the `pricing` module. It is deliberately free of
implementation detail; it is the single source from which the EP, BVA, CEG and
MC/DC test suites are derived.

Provenance: the module under test is `tss/lab/pricing.py`, ported
behavior-identically from `momentstudio/backend/app/services/pricing.py` (the
team's own repository). Honesty note: the program pre-dates this lab, so this
specification was derived from the module's observable behavior rather than
written before it; the assignment note permits declaring a bounded scope (not
spec-after-code reuse as such) — the provenance and the mitigation (black-box
wording only; all suites derived from this SPEC, never from the code) are
stated in [`README.md`](README.md) "Provenance, stated plainly".

---

## 1. Scope

The analysis scope is the **whole pricing module**: the four public callables
`quantize_money`, `compute_fee`, `compute_vat`, `compute_totals` and the result
record `PricingBreakdown` (~4 functions, declared per the assignment note).
All functions are pure: no I/O, no global state, no side effects; identical
inputs always produce identical outputs.

## 2. Public interface summary

| Callable | Keyword-only inputs | Output |
|---|---|---|
| `quantize_money` | `value: Decimal`, `rounding: str = "half_up"` | `Decimal` with exactly 2 decimal places |
| `compute_fee` | `taxable_subtotal: Decimal`, `enabled: bool`, `fee_type: str`, `fee_value: Decimal`, `rounding: str = "half_up"` | `Decimal` (2 dp) |
| `compute_vat` | `taxable_subtotal`, `shipping`, `fee: Decimal`, `enabled: bool`, `vat_rate_percent: Decimal`, `apply_to_shipping: bool`, `apply_to_fee: bool`, `rounding: str = "half_up"` | `Decimal` (2 dp) |
| `compute_totals` | `subtotal`, `discount`, `shipping: Decimal`, `fee_enabled: bool`, `fee_type: str`, `fee_value: Decimal`, `vat_enabled: bool`, `vat_rate_percent: Decimal`, `vat_apply_to_shipping: bool`, `vat_apply_to_fee: bool`, `rounding: str = "half_up"`, `vat_override: Decimal or None` | `PricingBreakdown` |
| `PricingBreakdown` | frozen dataclass with fields `subtotal`, `discount`, `taxable_subtotal`, `shipping`, `fee`, `vat`, `total` (all `Decimal`) | — |

All money/rate inputs are `Decimal` values. Integer inputs are accepted and
treated as exact money amounts. All function parameters are keyword-only.

## 3. Input domains

| Input | Type / domain | Valid partitions |
|---|---|---|
| money inputs (`subtotal`, `discount`, `shipping`, `taxable_subtotal`, `fee_value`, `fee`, `vat_override`) | `Decimal` | negative / zero / positive; and for each: sub-cent precision (> 2 dp) vs. exact 2 dp vs. whole units |
| `fee_value` (as percent) | `Decimal` | e.g. 0 < p < 100, p ≥ 100 (percent above 100 is not rejected) |
| `vat_rate_percent` | `Decimal` | < 0, = 0, 0 < r, r ≥ 100 allowed |
| booleans (`enabled`, `fee_enabled`, `vat_enabled`, `apply_to_shipping`, `apply_to_fee`, `vat_apply_to_shipping`, `vat_apply_to_fee`) | `bool` | true / false |
| `fee_type` | `str` | `"flat"` / `"percent"` — **any other string behaves like `"flat"`** (only `"percent"` triggers percentage computation; there is no validation error) |
| `rounding` | `str` | `"half_up"` / `"half_even"` / `"up"` / `"down"` — **any unrecognized value falls back to `half_up`** (no error) |
| `vat_override` | `Decimal` or `None` | `None` (VAT computed) / present (VAT taken from override, clamped) |

## 4. Rounding rules (`quantize_money`)

R1. Every monetary result carries **exactly two decimal places** (nearest cent,
    quantum 0.01).
R2. `rounding` selects the tie/rounding policy applied at the third decimal:
    - `"half_up"` (default): ties go away from zero — `2.345 → 2.35`,
      `-2.345 → -2.35`.
    - `"half_even"` (banker's): ties go to the even cent — `2.345 → 2.34`,
      `2.355 → 2.36`.
    - `"up"`: always away from zero at the cut digit — `2.341 → 2.35`.
    - `"down"`: always toward zero (truncate) — `2.349 → 2.34`.
R3. An unrecognized `rounding` value is **not** an error: the function behaves
    exactly as `"half_up"` (silent fallback).
R4. Rounding is idempotent for values already at 2 dp.

## 5. Fee rules (`compute_fee`)

F1. If `enabled` is false, the fee is `0.00` (all other fee inputs ignored).
F2. If `fee_value ≤ 0`, the fee is `0.00` (a non-positive fee is never charged;
    zero and negative fee values are treated identically).
F3. If `fee_type == "percent"`: fee = round(`taxable_subtotal` × `fee_value` / 100)
    using the selected rounding mode.
F4. Otherwise (`"flat"` and any other string): fee = round(`fee_value`).
F5. Fee results are always ≥ 0 whenever `fee_value` > 0 (percent fee on a
    non-negative subtotal cannot be negative).

## 6. VAT rules (`compute_vat`)

V1. If `enabled` is false, VAT is `0.00`.
V2. If `vat_rate_percent ≤ 0`, VAT is `0.00`.
V3. The VAT base starts at `taxable_subtotal`; `shipping` is added iff
    `apply_to_shipping` is true; `fee` is added iff `apply_to_fee` is true
    (both may be added, either, or neither).
V4. If the composed base ≤ 0, VAT is `0.00` (no negative or zero VAT is
    computed, even with a positive rate).
V5. Otherwise VAT = round(base × `vat_rate_percent` / 100) using the selected
    rounding mode.

## 7. Totals composition (`compute_totals`)

T1. `subtotal` is quantized to the cent (`subtotal_q`); it is reported as-is
    even if negative (no clamping on the reported subtotal).
T2. `discount` contributes only when positive: a discount ≤ 0 reports as
    `0.00`; a positive discount is quantized to the cent.
T3. `taxable_subtotal = max(0, subtotal_q − discount_q)`, re-quantized
    (a discount larger than the subtotal floors the taxable amount at `0.00`;
    the excess discount is *not* refunded anywhere else).
T4. `shipping` contributes only when positive (≤ 0 reports as `0.00`);
    otherwise quantized to the cent.
T5. `fee` is derived from the *taxable* subtotal via the fee rules (F1–F5)
    with `enabled = fee_enabled`.
T6. VAT resolution order:
    - `vat_enabled` false → VAT is `0.00` (an override, if supplied, is ignored);
    - else if `vat_override` is supplied (not `None`) → VAT = round(max(0,
      `vat_override`)) (non-positive overrides clamp to `0.00`;
      `vat_rate_percent`/apply flags are ignored);
    - else VAT is computed by the VAT rules (V1–V5) on base
      = taxable [+ shipping if `vat_apply_to_shipping`] [+ fee if
      `vat_apply_to_fee`].
T7. `total = taxable_subtotal + shipping + fee + vat`, then quantized to the
    cent. All summands are non-negative by rules T3–T6, so the total is always
    ≥ `0.00` (the module guarantees a non-negative total by construction).
T8. The returned `PricingBreakdown` reports: `subtotal` (T1), `discount` (T2),
    `taxable_subtotal` (T3), `shipping` (T4), `fee` (T5), `vat` (T6),
    `total` (T7). The record is immutable (frozen).

## 8. Error behavior

E1. The module defines **no domain-level errors**: no raised domain exceptions,
    no `NaN`/`Infinity` outputs for valid `Decimal` inputs, no logging.
E2. Zero-division never occurs (divisors are the constant 100).
E3. Malformed inputs surface as standard-library exceptions, unmodified:
    - a non-numeric object where `Decimal` arithmetic is required raises
      `TypeError` (or `decimal.InvalidOperation` for non-numeric strings);
    - values whose cent-quantized magnitude exceeds the decimal context
      precision (default 28 significant digits) raise
      `decimal.InvalidOperation` from the quantization step.
E4. Out-of-vocabulary `fee_type` / `rounding` strings are *not* errors
    (see R3 and §3).

## 9. Derivation anchors (for the test-design suites)

- **EP (equivalence partitioning)**: the partitions of §3 crossed with rule
  families F/V/T — one representative per partition per rule.
- **BVA (boundary value analysis)**: the clamping boundaries `discount = 0`,
  `shipping = 0`, `fee_value = 0`, `vat_rate_percent = 0`, `taxable = 0`
  (discount = subtotal), `base = 0` in V4, `vat_override = 0`, plus the
  cent-tie boundaries `x.xx5` and `x.xx49/x.xx51`-style third-decimal values
  for each rounding mode (R2). On each boundary: below / at / above.
- **CEG (cause–effect)**: causes are the boolean and sign conditions
  (`fee_enabled`, `fee_value > 0`, `fee_type == "percent"`, `vat_enabled`,
  `vat_rate_percent > 0`, `apply_to_shipping`, `apply_to_fee`, `base > 0`,
  `vat_override is not None`, `vat_override > 0`, `discount > 0`,
  `shipping > 0`); effects are the observable outputs `fee == 0`,
  `vat == 0`, `vat` computed from base/override, `taxable` floored, and the
  `total` identity of T7. A decision table over these causes generates the
  CEG constraints (impossible combinations excluded, e.g. `vat_enabled=false`
  together with any VAT-output effect other than `vat == 0.00`).
- **MC/DC**: the compound decisions of `compute_totals` — the three-way VAT
  branch (T6: `not vat_enabled` / `vat_override is not None` / else) and the
  guard `vat_override > 0` inside the override arm; the discount/shipping
  contribution decisions (T2/T4) — each independently varying its outcome
  while holding the others fixed.
