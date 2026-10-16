# BVA — Boundary Value Analysis derivation for `tss/lab/pricing.py`

Suite: `tss/lab/tests/test_bva.py` · Technique: BVA only (per SPEC.md §9 BVA anchor).
Module under test: `tss/lab/pricing.py` (frozen; black-box, spec-driven).
Source of truth: `tss/lab/SPEC.md` (requirements baseline v1, 2026-10-16).

All inputs and expected outputs below are exact `Decimal` values. Every assertion
in the suite is exact `Decimal` equality (numeric `==`); two-decimal-place shape
(SPEC R1) is additionally asserted via `as_tuple().exponent == -2`.

## 1. Neighbor strategy (min, min+, nom, max−, max analog)

The input domain of §3 has **no finite upper bound** (no max subtotal/rate/fee is
specified), so the classic 5-point pattern degenerates for range boundaries.
The finite boundaries the spec does define are of two kinds:

1. **Clamp/sign boundaries at 0** — discount, shipping, fee_value,
   vat_rate_percent, taxable subtotal, composed VAT base, vat_override, and the
   subtotal sign boundary (negative/zero/positive).
2. **Cent-tie boundaries at the third decimal** (`x.xx5`) for each rounding mode
   (R2), and the cent quantum itself (0.01, R1/R4).

For each boundary point `B` we test the 3-point neighbor set
`{B−, B, B+}` where the step is the smallest spec-meaningful increment:

- For clamp boundaries: sub-cent neighbors `B ± 0.001` (and `± 0.01`, `± 1`
  where sign behavior, not sub-cent behavior, is the subject).
- For tie boundaries: the 5-point analog `{x.xx4, x.xx49, x.xx5, x.xx51, x.xx6}`
  — i.e. one cent below, a fine sub-tie step below, the tie itself, a fine
  step above, one cent above — which fills the min/min+/nom/max−/max roles.
- For the cent quantum: `{0.004, 0.005, 0.006}` around the smallest surviving
  cent `0.01`.

## 2. Boundary inventory and expected values

### B1. `quantize_money` cent tie, positive values (R2)

Raw value `2.345` neighborhood; expected per mode:

| value | half_up | half_even | up | down | rule |
|---|---|---|---|---|---|
| 2.344 | 2.34 | 2.34 | 2.35 | 2.34 | R2 |
| 2.3449 | 2.34 | 2.34 | 2.35 | 2.34 | R2 |
| 2.345 (tie) | **2.35** | **2.34** | 2.35 | 2.34 | R2 (tie splits the modes) |
| 2.3451 | 2.35 | 2.35 | 2.35 | 2.34 | R2 |
| 2.346 | 2.35 | 2.35 | 2.35 | 2.34 | R2 |

### B2. `quantize_money` cent tie, negative mirror (R2: ties away/toward zero)

| value | half_up | half_even | up | down |
|---|---|---|---|---|
| −2.344 | −2.34 | −2.34 | −2.35 | −2.34 |
| −2.345 (tie) | **−2.35** | **−2.34** | −2.35 | −2.34 |
| −2.346 | −2.35 | −2.35 | −2.35 | −2.34 |

### B3. `half_even` even-vs-odd tie pair (R2)

`2.345 → 2.34` (4 even), `2.355 → 2.36` (6 even), `−2.345 → −2.34`,
`−2.355 → −2.36`.

### B4. Smallest surviving cent — quantum boundary at 0.01 (R1, R2)

| value | half_up | half_even | up | down |
|---|---|---|---|---|
| 0.004 | 0.00 | 0.00 | 0.01 | 0.00 |
| 0.005 (tie) | **0.01** | **0.00** (0 is even) | 0.01 | 0.00 |
| 0.006 | 0.01 | 0.01 | 0.01 | 0.00 |

`0.005` under `half_up` is the minimum positive magnitude that survives
quantization; under `down` nothing sub-cent survives.

### B5. Two-dp shape + idempotency at the boundary (R1, R4)

Representatives `0 → 0.00`, `2 → 2.00`, `2.35 → 2.35`, `−2.35 → −2.35`,
`123.45 → 123.45`, `−123.45 → −123.45` (the last two add wider-magnitude
2-dp shapes): output exponent exactly −2 under all four modes; quantizing an
already-2-dp value is the identity under all four modes (double quantization
= single). These are exactly the six values parametrized in
`tests/test_bva.py::test_b5_two_dp_shape_and_idempotency`.

### B6. Unrecognized rounding mode at the tie (R3)

At the tie `2.345`, `"bogus"` and `""` both behave exactly as `half_up` → 2.35;
below the tie (`2.344`) → 2.34. (Fallback probed *at* the boundary where mode
behavior is distinguishable.)

### B7. `compute_fee` — `fee_value = 0` clamp (F2), flat fee

`taxable_subtotal = 100`, `enabled = True`, `fee_type = "flat"`:

| fee_value | fee (half_up) | note |
|---|---|---|
| −0.01 | 0.00 | below |
| −0.001 | 0.00 | below (fine) |
| 0 / 0.00 | 0.00 | at |
| 0.001 | 0.00 | above, but quantizes to 0.00 (B4 interaction) |
| 0.004 | 0.00 | above, fine |
| 0.005 | **0.01** | min surviving positive fee (half_up); → 0.00 under `down` |

### B8. `compute_fee` — `fee_value = 0` clamp (F2), percent fee

`taxable_subtotal = 100`, `fee_type = "percent"`:

| fee_value | fee (half_up) |
|---|---|
| −1 / −0.001 / 0 | 0.00 |
| 0.001 | 0.00 (100 × 0.001/100 = 0.001 → 0.00) |
| 0.005 | 0.01 (100 × 0.005/100 = 0.005 tie → up) |

### B9. `compute_fee` — flat sub-cent tie (F4)

`fee_value = 2.345`: half_up 2.35 / half_even 2.34 / up 2.35 / down 2.34;
neighbors 2.344 → 2.34 and 2.346 → 2.35 under half_up.

### B10. `compute_fee` — percent tie (F3) and taxable sign boundary (F3/F5)

Tie: `taxable_subtotal = 23.45`, `fee_value = 10` → raw `2.345` →
half_up 2.35 / half_even 2.34 / up 2.35 / down 2.34; neighbors 23.44 → 2.34,
23.46 → 2.35 (half_up).

Sign boundary around `taxable_subtotal = 0` (`fee_value = 10`, percent):

| taxable | fee |
|---|---|
| −100 | −10.00 (spec F5 only guarantees ≥ 0 for non-negative subtotals) |
| −0.001 | 0.00 (−0.0001 → quantized −0.00) |
| 0 | 0.00 |
| 0.001 | 0.00 (0.0001 → 0.00) |
| 100 | 10.00 |

### B11. `compute_vat` — `vat_rate_percent = 0` clamp (V2)

Base fixed at `taxable_subtotal = 100`, no shipping/fee:

| rate | vat (half_up) |
|---|---|
| −1 / −0.001 | 0.00 |
| 0 / 0.00 | 0.00 |
| 0.001 | 0.00 (100 × 0.001/100 = 0.001) |
| 0.004 | 0.00 |
| 0.005 | **0.01** (minimum rate yielding nonzero VAT at base 100, half_up); → 0.00 under `down` |

### B12. `compute_vat` — composed `base = 0` clamp (V4)

Rate 100 (vat = base), `taxable_subtotal = 100`, `apply_to_shipping = True`:

| shipping | base | vat |
|---|---|---|
| −100.01 | −0.01 | 0.00 |
| −100.001 | −0.001 | 0.00 |
| −100.00 | 0 | 0.00 |
| −99.999 | 0.001 | 0.00 (0.001 → 0.00) |
| −99.99 | 0.01 | **0.01** (smallest surviving positive base) |

Direct base boundary (no shipping/fee): taxable −0.01 / 0 / 0.01 →
0.00 / 0.00 / 0.01.

### B13. `compute_vat` — rate tie at the third decimal (V5)

`taxable_subtotal` varies, rate 10, raw = taxable × 0.1:

| taxable | raw | half_up | half_even | up | down |
|---|---|---|---|---|---|
| 23.44 | 2.344 | 2.34 | 2.34 | 2.35 | 2.34 |
| 23.45 | 2.345 | 2.35 | 2.34 | 2.35 | 2.34 |
| 23.46 | 2.346 | 2.35 | 2.35 | 2.35 | 2.34 |

### B14. `compute_totals` — `discount = 0` clamp (T2)

`subtotal = 100`, everything else off (fee off, vat off, shipping 0):

| discount | reported discount | taxable | total |
|---|---|---|---|
| −0.01 / −0.001 | 0.00 | 100.00 | 100.00 |
| 0 / 0.00 | 0.00 | 100.00 | 100.00 |
| 0.001 | 0.00 | 100.00 | 100.00 |
| 0.004 | 0.00 | 100.00 | 100.00 |
| 0.005 | **0.01** (half_up) | 99.99 | 99.99 |

`down` variant: discount 0.005 → reported 0.00, taxable 100.00.

### B15. `compute_totals` — `taxable = 0` floor via `discount = subtotal` (T3)

`subtotal = 100`:

| discount | reported discount | taxable | total |
|---|---|---|---|
| 99.99 | 99.99 | **0.01** (smallest non-floored) | 0.01 |
| 100.00 | 100.00 | 0.00 | 0.00 |
| 100.01 | 100.01 (reported as-is; excess not refunded, T3) | 0.00 | 0.00 |

### B16. `compute_totals` — `shipping = 0` clamp (T4)

`subtotal = 100`, fee off, vat off:

| shipping | reported shipping | total |
|---|---|---|
| −0.01 / −0.001 | 0.00 | 100.00 |
| 0 | 0.00 | 100.00 |
| 0.001 | 0.00 | 100.00 |
| 0.005 | **0.01** (half_up); 0.00 under `down` | 100.01 |

### B17. `compute_totals` — subtotal sign boundary (T1, T3, T7)

Everything else off:

| subtotal | reported subtotal | taxable | total |
|---|---|---|---|
| −10.00 | −10.00 (reported as-is, T1) | 0.00 (floored, T3) | 0.00 (≥ 0, T7) |
| −0.01 | −0.01 | 0.00 | 0.00 |
| 0 | 0.00 | 0.00 | 0.00 |
| 0.01 | 0.01 | 0.01 | 0.01 |

### B18. `compute_totals` — `vat_override = 0` clamp + sub-cent (T6)

`subtotal = 100`, `vat_enabled = True`, `vat_rate_percent = 10` (computed VAT
would be 10.00 — the override arm must suppress it):

| vat_override | vat (half_up) |
|---|---|
| −0.01 / −0.001 | 0.00 |
| 0 / 0.00 | 0.00 |
| 0.001 / 0.004 | 0.00 |
| 0.005 | **0.01**; → 0.00 under `down` |
| 2.345 (tie) | 2.35 / 2.34 / 2.35 / 2.34 (half_up / half_even / up / down) |

### B19. `compute_totals` — override-vs-computed switch points (T6)

`subtotal = 100`, `vat_rate_percent = 10`, fee off, shipping 0:

| vat_enabled | vat_override | vat | total |
|---|---|---|---|
| True | None | 10.00 (computed) | 110.00 |
| True | `0.00` | 0.00 (**presence** of a zero override switches off computation) | 100.00 |
| True | `5.00` | 5.00 (rate ignored) | 105.00 |
| False | `5.00` | 0.00 (enabled gate wins over override) | 100.00 |
| False | None | 0.00 | 100.00 |

### B20. `compute_totals` — minimal-sum and all-zero totals (T7)

- All summands at the minimum surviving cent: `subtotal = 0.01`,
  `shipping = 0.01`, flat fee `0.01`, vat override `0.01` → total **0.04**;
  each field exactly 2 dp.
- All-off zero row (`subtotal = 0`, everything disabled/zero) → every field
  `0.00`, total `0.00`, exponent −2.

## 3. Out of scope (owned by other suites)

Equivalence-class representatives away from boundaries (EP), boolean
cause–effect decision tables (CEG), and condition/decision independence of the
T6 branch arms (MC/DC) are covered by their own suites; B19's switch points are
the *value boundaries* of the switch, not its MC/DC condition analysis.
