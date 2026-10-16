# EP — Equivalence Partitioning derivation for `pricing`

Technique: **equivalence partitioning (EP)**, derived from
[`tss/lab/SPEC.md`](../SPEC.md) §3 (input domains), §4–§7 (rule families
R/F/V/T), §8 (error classes), per the §9 EP anchor: *"the partitions of §3
crossed with rule families F/V/T — one representative per partition per
rule."*

Method:

- Every input of the four public callables is partitioned into classes from
  the SPEC's own domain definitions; each class gets **one representative**
  (occasionally a second representative where the SPEC explicitly declares two
  sign classes *identical*, to evidence the merge).
- Expected outcomes are computed from the SPEC rules only (F1–F5, V1–V5,
  T1–T8, R1–R4, E3), not from the implementation.
- Where a SPEC rule merges the zero and negative members of a money input
  into one class (`≤ 0`), the table records the merge (F2, T2, T4, T6) and
  the test uses both a zero and a negative representative of that single
  class.
- Boundary probing (below/at/above 0, `x.xx5 ± ε` sweeps) is **BVA's** job and
  is deliberately absent: representatives are mid-class values (discount
  150 vs subtotal 100 for the T3 floor class, not 100.00±ε; the SPEC's own
  R2 tie examples are used once each as the canonical representative of a
  rounding-mode class). Decision tables over boolean causes are CEG's job;
  condition-isolating minimal pairs are MC/DC's job — each boolean class
  appears here exactly once, inside an otherwise-neutral scenario.

All monetary assertions are exact `Decimal` equality; R1's "exactly two
decimal places" is additionally pinned by an exponent check
(`as_tuple().exponent == -2`).

---

## 1. Partition tables

### 1.1 `rounding` (keyword input of all four callables) — SPEC §3, R2–R3

| # | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| R-1 | `"half_up"` | `2.345` and `-2.345` | R2 | `2.35` / `-2.35` (ties away from zero) | `test_q_rounding_half_up_tie` |
| R-2 | `"half_even"` | `2.345` and `2.355` | R2 | `2.34` / `2.36` (ties to even cent) | `test_q_rounding_half_even_tie` |
| R-3 | `"up"` | `2.341` | R2 | `2.35` (away from zero at cut digit) | `test_q_rounding_up` |
| R-4 | `"down"` | `2.349` | R2 | `2.34` (truncate toward zero) | `test_q_rounding_down` |
| R-5 | unrecognized string | `"bogus"`, `""` | R3 | silent fallback, identical to `half_up`: `2.345 → 2.35` | `test_q_rounding_unknown_falls_back_half_up` |
| R-6 | omitted (default argument class) | — | §2 | same as `"half_up"`: `2.345 → 2.35` | `test_q_rounding_default_is_half_up` |
| R-7 | mode propagates into `compute_fee` (flat) | `7.779`, `"down"` | F4 | `7.77` (vs `7.78` under half_up) | `test_f_rounding_propagates_down_flat` |
| R-8 | mode propagates into `compute_fee` (percent) | `100.05 × 10/100 = 10.005`, `"up"` | F3 | `10.01` | `test_f_rounding_propagates_up_percent` |
| R-9 | mode propagates into `compute_vat` | `100.05 × 10/100 = 10.005`, `"down"` | V5 | `10.00` | `test_v_rounding_propagates_down` |
| R-10 | mode propagates into `compute_totals` | flat fee `7.779`, `"down"` | T5/T7 | fee `7.77`, total `107.77` | `test_t_rounding_propagates_in_totals` |

### 1.2 `quantize_money` value classes — SPEC §3 money, R1/R4, §2, E3

| # | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| Q-1 | positive, whole units | `10` | R1 | `10.00` | `test_q_value_positive_whole_units` |
| Q-2 | positive, exact 2 dp | `12.34` | R4 | `12.34` (idempotent) | `test_q_value_positive_exact_2dp_idempotent` |
| Q-3 | positive, >2 dp sub-cent | `2.345`-family | R2 | mode-dependent (rows R-1…R-5) | covered by §1.1 |
| Q-4 | zero | `0` | R1 | `0.00` | `test_q_value_zero` |
| Q-5 | negative | `-7` | R1 | `-7.00` (2 dp preserved, sign kept) | `test_q_value_negative_whole` |
| Q-6 | integer type accepted | `5` (Python `int`) | §2 | `5.00` (treated as exact money) | `test_q_integer_input_accepted` |
| Q-7 | output invariant: 2 decimal places | battery of results | R1 | every result exponent `-2` | `test_q_r1_exponent_two_dp` |
| Q-8 | invalid: non-numeric string | `"abc"` | E3 | `decimal.InvalidOperation` unmodified | `test_q_invalid_nonnumeric_string_raises_invalidoperation` |
| Q-9 | invalid: non-numeric object | `object()` | E3 | `TypeError` unmodified | `test_q_invalid_nonnumeric_object_raises_typeerror` |

### 1.3 `fee_type` — SPEC §3

| # | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| T-1 | `"percent"` | `taxable=100.00`, `p=10` | F3 | fee = round(`100×10/100`) = `10.00` | `test_f3_percent_below_100` |
| T-2 | `"flat"` | `fee_value=7.777` | F4 | fee = round(`7.777`) = `7.78` | `test_f4_flat_quantizes_fee_value` |
| T-3 | any other string (no validation error) | `"FIXED"` | §3/F4 | behaves like flat: `7.777 → 7.78` | `test_f4_other_fee_type_behaves_flat` |

### 1.4 `enabled` flags — F1 / V1 / T5 / T6

| # | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| E-1 | `compute_fee(enabled=False)` | `percent`, `fee_value=9999`, `taxable=1000000` | F1 | `0.00`; all other fee inputs ignored | `test_f1_enabled_false_zero_regardless` |
| E-2 | `compute_vat(enabled=False)` | rate `25`, positive base parts | V1 | `0.00` | `test_v1_enabled_false_zero_regardless` |
| E-3 | `compute_totals(fee_enabled=False)` | `percent 50` on subtotal `100` | F1 via T5 | fee `0.00` in breakdown | `test_t5_fee_disabled_zero_in_totals` |
| E-4 | `compute_totals(vat_enabled=False)` | with `vat_override=99.00` supplied | T6 (1st arm) | vat `0.00`; **override ignored** | `test_t6_vat_disabled_ignores_override` |

### 1.5 apply flags (`apply_to_shipping` × `apply_to_fee`, and the totals-level `vat_apply_*`) — V3

| # | Class | Representative (taxable=100.00, shipping=20.00, fee=10.00, rate 25) | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| A-1 | neither applied | `(False, False)` | V3 | base `100` → `25.00` | `test_v5_rate_below_100_no_extras` |
| A-2 | shipping only | `(True, False)` | V3 | base `120` → `30.00` | `test_v3_apply_shipping_only` |
| A-3 | fee only | `(False, True)` | V3 | base `110` → `27.50` | `test_v3_apply_fee_only` |
| A-4 | both | `(True, True)` | V3 | base `130` → `32.50` | `test_v3_apply_both` |
| A-5 | totals-level flags (both true, computed path) | `None` override, rate 10 | T6 (3rd arm) | base `130` → vat `13.00` | `test_t6_none_override_computed_with_apply_flags` |

### 1.6 money inputs, sign/zero/precision classes — §3 crossed with F/V/T

| # | Input | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|---|
| M-1 | `taxable_subtotal` (fee) | positive | `100.00`, `p=10` | F3 | `10.00` | `test_f3_percent_below_100` |
| M-2 | `taxable_subtotal` (fee) | zero | `0`, `p=10` | F3 | `0.00` | `test_f3_percent_zero_taxable` |
| M-3 | `taxable_subtotal` (fee) | negative | `-100.00`, `p=10` | F3 formula | `-10.00` (F5 only guards non-negative subtotals) | `test_f3_percent_negative_taxable` |
| M-4 | `fee_value` | `≤ 0` — SPEC F2: *zero and negative treated identically* (one class) | `0` and `-10` | F2 | `0.00` for both | `test_f2_fee_value_nonpositive_zero` |
| M-5 | `fee_value` as percent | `0 < p < 100` | `p=10` | F3 | percent fee computed | `test_f3_percent_below_100` |
| M-6 | `fee_value` as percent | `p ≥ 100` (not rejected) | `p=150`, taxable `50` | F3 | `75.00` | `test_f3_percent_at_or_above_100` |
| M-7 | `fee_value` precision | >2 dp | `7.777` | F4 | quantized `7.78` | `test_f4_flat_quantizes_fee_value` |
| M-8 | `taxable_subtotal` (vat) | positive | `100.00` @25 | V5 | `25.00` | `test_v5_rate_below_100_no_extras` |
| M-9 | `taxable_subtotal` (vat) | ≤ 0 (zero & negative) | `-50`; `0` | V4 | `0.00` both | `test_v4_base_nonpositive_zero` |
| M-10 | `shipping` (vat base) | negative, applied | `taxable=30`, `shipping=-10`, `(T,F)` @25 | V3 | base `20` → `5.00` | `test_v3_negative_shipping_reduces_base` |
| M-11 | `fee` (vat base) | negative, applied | `taxable=30`, `fee=-10`, `(F,T)` @25 | V3 | base `20` → `5.00` (same class as M-10, other slot) | `test_v3_negative_shipping_reduces_base` |
| M-12 | `subtotal` | positive, >2 dp | `100.009` | T1 | quantized `100.01`, total `100.01` | `test_t1_subcent_subtotal_quantized` |
| M-13 | `subtotal` | zero | `0` | T1/T3 | subtotal `0.00`, taxable `0.00`, total `0.00` | `test_t1_zero_subtotal` |
| M-14 | `subtotal` | negative | `-50` | T1 | reported as-is `-50.00`; taxable floored `0.00`; total `0.00` | `test_t1_negative_subtotal_reported_as_is` |
| M-15 | `discount` | positive | `100`, `d=20` | T2 | discount `20.00`, taxable `80.00` | `test_t2_positive_discount_applied` |
| M-16 | `discount` | positive, >2 dp | `d=20.005` | T2 | discount `20.01`, taxable `79.99` | `test_t2_subcent_discount_quantized` |
| M-17 | `discount` | `≤ 0` — T2 merges zero/negative into one class | `0` and `-10` | T2 | reported `0.00`, taxable unchanged `100.00` | `test_t2_nonpositive_discount_ignored` |
| M-18 | `discount` | > subtotal | `d=150` vs subtotal `100` | T3 | taxable floored `0.00`; excess not refunded; total `10.00` (shipping only) | `test_t3_discount_exceeding_subtotal_floors_taxable` |
| M-19 | `shipping` (totals) | positive, >2 dp | `5.555` | T4 | shipping `5.56`, total `105.56` | `test_t4_positive_shipping_quantized` |
| M-20 | `shipping` (totals) | `≤ 0` — T4 merges zero/negative into one class | `0` and `-3` | T4 | reported `0.00`, total `100.00` | `test_t4_nonpositive_shipping_zero` |
| M-21 | `vat_override` | `None` | — | T6 (3rd arm) | VAT computed from base/flags | `test_t6_none_override_computed_with_apply_flags` |
| M-22 | `vat_override` | present, positive | `12.345` (rate `0`, flags off) | T6 (2nd arm) | VAT = round(override) = `12.35`; rate/flags ignored; total `112.35` | `test_t6_positive_override_used_rate_ignored` |
| M-23 | `vat_override` | present, `≤ 0` — T6 clamps zero and negative identically | `0` and `-4` | T6 (2nd arm) | VAT `0.00` | `test_t6_nonpositive_override_clamped` |

### 1.7 `vat_rate_percent` — §3 / V2 / V5

| # | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| VR-1 | `r < 0` | `-5` (base 100) | V2 | `0.00` | `test_v2_rate_nonpositive_zero` |
| VR-2 | `r = 0` | `0` (base 100) | V2 | `0.00` (same class as VR-1 per `≤ 0` rule; both reps asserted) | `test_v2_rate_nonpositive_zero` |
| VR-3 | `0 < r < 100` | `25` (base 100) | V5 | `25.00` | `test_v5_rate_below_100_no_extras` |
| VR-4 | `r ≥ 100` (allowed) | `150` (base 100) | V5 | `150.00` | `test_v5_rate_at_or_above_100` |

### 1.8 totals composition / output-record classes — T1–T8

| # | Class | Representative | Rule | Expected outcome | Test |
|---|---|---|---|---|---|
| C-1 | fee derived from *taxable*, not subtotal | subtotal `200`, discount `150` → taxable `50`, percent `10` | T5 | fee `5.00`, total `55.00` | `test_t5_fee_computed_from_taxable_not_subtotal` |
| C-2 | full composition identity | sub `200`, disc `50`, ship `20`, fee percent `10`, VAT `10` on (taxable+ship+fee) | T7 | taxable `150`, fee `15.00`, vat `18.50`, **total = 150+20+15+18.50 = `203.50`** | `test_t7_total_identity_full_scenario` |
| C-3 | record reports all 8 fields | same scenario | T8 | every field asserted (folded into C-2's test) | `test_t7_total_identity_full_scenario` |
| C-4 | record immutable | setattr on `PricingBreakdown` | T8 | `dataclasses.FrozenInstanceError` | `test_t8_breakdown_frozen` |

---

## 2. Test inventory (52 tests, `tests/test_ep.py`)

`quantize_money` (14): Q-1…Q-9 rows → `test_q_*`.
`compute_fee` (10): E-1, M-2…M-7, T-1…T-3, R-7, R-8 → `test_f*`.
`compute_vat` (10): E-2, A-1…A-4, M-9…M-11, VR-1…VR-4, R-9 → `test_v*`.
`compute_totals` (18): E-3, E-4, A-5, M-12…M-23, C-1…C-4, R-10 → `test_t*`.

Every class row above has at least one test; no test exercises another
technique's space (no ±ε sweeps, no decision-table combinations, no
condition-isolation pairs).
