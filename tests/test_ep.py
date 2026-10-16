"""EP (equivalence partitioning) suite — derived from SPEC.md §3 + §9.

One representative per equivalence class (occasionally a second representative
where the SPEC explicitly declares two sign classes identical — F2, T2, T4,
T6 — to evidence the merge). Expected values are computed from the SPEC rules
(R1-R4, F1-F5, V1-V5, T1-T8, E3), not from the implementation.

Derivation table: tss/lab/docs/ep.md.

Scope discipline: EP only. No boundary ±ε sweeps (BVA), no boolean
decision-table combinations (CEG), no condition-isolation pairs (MC/DC).
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal, InvalidOperation

import pytest

from pricing import PricingBreakdown, compute_fee, compute_totals, compute_vat, quantize_money


def _totals(**overrides):
    """compute_totals with neutral defaults (everything off/zero, half_up).

    Each test overrides exactly the inputs whose classes it exercises, so
    every test is independent and scenario-neutral.
    """
    args = dict(
        subtotal=Decimal("0"),
        discount=Decimal("0"),
        shipping=Decimal("0"),
        fee_enabled=False,
        fee_type="flat",
        fee_value=Decimal("0"),
        vat_enabled=False,
        vat_rate_percent=Decimal("0"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=False,
        rounding="half_up",
        vat_override=None,
    )
    args.update(overrides)
    return compute_totals(**args)


# ---------------------------------------------------------------------------
# quantize_money — value classes (Q-1..Q-9) and rounding-mode classes (R-1..R-6)
# ---------------------------------------------------------------------------


def test_q_value_positive_whole_units():
    # Q-1: positive whole units -> exactly 2 dp (R1)
    assert quantize_money(Decimal("10")) == Decimal("10.00")


def test_q_value_positive_exact_2dp_idempotent():
    # Q-2: already at 2 dp -> unchanged (R4)
    assert quantize_money(Decimal("12.34")) == Decimal("12.34")


def test_q_value_zero():
    # Q-4: zero -> 0.00 (R1)
    assert quantize_money(Decimal("0")) == Decimal("0.00")


def test_q_value_negative_whole():
    # Q-5: negative -> sign kept, 2 dp (R1)
    assert quantize_money(Decimal("-7")) == Decimal("-7.00")


def test_q_rounding_half_up_tie():
    # R-1: half_up, ties away from zero (R2)
    assert quantize_money(Decimal("2.345"), rounding="half_up") == Decimal("2.35")
    assert quantize_money(Decimal("-2.345"), rounding="half_up") == Decimal("-2.35")


def test_q_rounding_half_even_tie():
    # R-2: banker's rounding, ties to the even cent (R2)
    assert quantize_money(Decimal("2.345"), rounding="half_even") == Decimal("2.34")
    assert quantize_money(Decimal("2.355"), rounding="half_even") == Decimal("2.36")


def test_q_rounding_up():
    # R-3: always away from zero at the cut digit (R2)
    assert quantize_money(Decimal("2.341"), rounding="up") == Decimal("2.35")


def test_q_rounding_down():
    # R-4: always toward zero / truncate (R2)
    assert quantize_money(Decimal("2.349"), rounding="down") == Decimal("2.34")


def test_q_rounding_unknown_falls_back_half_up():
    # R-5: unrecognized rounding is NOT an error — behaves as half_up (R3)
    assert quantize_money(Decimal("2.345"), rounding="bogus") == Decimal("2.35")
    assert quantize_money(Decimal("2.345"), rounding="") == Decimal("2.35")


def test_q_rounding_default_is_half_up():
    # R-6: rounding omitted (default-argument class) -> half_up behaviour
    assert quantize_money(Decimal("2.345")) == Decimal("2.35")


def test_q_integer_input_accepted():
    # Q-6: integer inputs accepted, treated as exact money (§2)
    assert quantize_money(5) == Decimal("5.00")


def test_q_r1_exponent_two_dp():
    # Q-7: R1 invariant — every monetary result carries exactly 2 decimal places
    for result in (
        quantize_money(Decimal("10")),
        quantize_money(Decimal("-7")),
        quantize_money(Decimal("0")),
        quantize_money(Decimal("2.349"), rounding="down"),
        quantize_money(Decimal("2.341"), rounding="up"),
    ):
        assert result.as_tuple().exponent == -2


def test_q_invalid_nonnumeric_string_raises_invalidoperation():
    # Q-8: malformed input surfaces as stdlib decimal.InvalidOperation (E3)
    with pytest.raises(InvalidOperation):
        quantize_money("abc")


def test_q_invalid_nonnumeric_object_raises_typeerror():
    # Q-9: non-numeric object surfaces as stdlib TypeError (E3)
    with pytest.raises(TypeError):
        quantize_money(object())


# ---------------------------------------------------------------------------
# compute_fee — fee_type / enabled / fee_value / taxable classes (F1-F5)
# ---------------------------------------------------------------------------


def test_f1_enabled_false_zero_regardless():
    # E-1: enabled=False -> 0.00, all other fee inputs ignored (F1)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("1000000"),
            enabled=False,
            fee_type="percent",
            fee_value=Decimal("9999"),
        )
        == Decimal("0.00")
    )


def test_f2_fee_value_nonpositive_zero():
    # M-4: fee_value <= 0 is ONE class — zero and negative treated
    # identically, both -> 0.00 (F2)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.00"),
            enabled=True,
            fee_type="flat",
            fee_value=Decimal("0"),
        )
        == Decimal("0.00")
    )
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.00"),
            enabled=True,
            fee_type="flat",
            fee_value=Decimal("-10"),
        )
        == Decimal("0.00")
    )


def test_f3_percent_below_100():
    # T-1/M-1/M-5: fee_type="percent", 0 < p < 100 (F3)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.00"),
            enabled=True,
            fee_type="percent",
            fee_value=Decimal("10"),
        )
        == Decimal("10.00")
    )


def test_f3_percent_at_or_above_100():
    # M-6: percent >= 100 is allowed, not rejected (F3, §3)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("50.00"),
            enabled=True,
            fee_type="percent",
            fee_value=Decimal("150"),
        )
        == Decimal("75.00")
    )


def test_f4_flat_quantizes_fee_value():
    # T-2/M-7: fee_type="flat" -> fee = round(fee_value); >2dp precision (F4)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.00"),
            enabled=True,
            fee_type="flat",
            fee_value=Decimal("7.777"),
        )
        == Decimal("7.78")
    )


def test_f4_other_fee_type_behaves_flat():
    # T-3: any string other than "percent" behaves like "flat", no error (§3/F4)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.00"),
            enabled=True,
            fee_type="FIXED",
            fee_value=Decimal("7.777"),
        )
        == Decimal("7.78")
    )


def test_f3_percent_zero_taxable():
    # M-2: taxable_subtotal zero, percent -> 0.00 (F3 formula)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("0"),
            enabled=True,
            fee_type="percent",
            fee_value=Decimal("10"),
        )
        == Decimal("0.00")
    )


def test_f3_percent_negative_taxable():
    # M-3: taxable_subtotal negative -> F3 formula yields a negative fee
    # (F5's non-negativity guarantee is scoped to non-negative subtotals)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("-100.00"),
            enabled=True,
            fee_type="percent",
            fee_value=Decimal("10"),
        )
        == Decimal("-10.00")
    )


def test_f_rounding_propagates_down_flat():
    # R-7: the selected rounding mode reaches compute_fee (flat, F4)
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.00"),
            enabled=True,
            fee_type="flat",
            fee_value=Decimal("7.779"),
            rounding="down",
        )
        == Decimal("7.77")
    )


def test_f_rounding_propagates_up_percent():
    # R-8: rounding reaches compute_fee (percent, F3): 100.05*10/100 = 10.005
    assert (
        compute_fee(
            taxable_subtotal=Decimal("100.05"),
            enabled=True,
            fee_type="percent",
            fee_value=Decimal("10"),
            rounding="up",
        )
        == Decimal("10.01")
    )


# ---------------------------------------------------------------------------
# compute_vat — enabled / rate / apply flags / base sign classes (V1-V5)
# ---------------------------------------------------------------------------


def _vat(**kw):
    args = dict(
        taxable_subtotal=Decimal("100.00"),
        shipping=Decimal("20.00"),
        fee=Decimal("10.00"),
        enabled=True,
        vat_rate_percent=Decimal("25"),
        apply_to_shipping=False,
        apply_to_fee=False,
        rounding="half_up",
    )
    args.update(kw)
    return compute_vat(**args)


def test_v1_enabled_false_zero_regardless():
    # E-2: enabled=False -> 0.00 (V1)
    assert _vat(enabled=False, vat_rate_percent=Decimal("25")) == Decimal("0.00")


def test_v2_rate_nonpositive_zero():
    # VR-1/VR-2: vat_rate_percent <= 0 is ONE class (V2): negative and zero
    # both -> 0.00
    assert _vat(vat_rate_percent=Decimal("0")) == Decimal("0.00")
    assert _vat(vat_rate_percent=Decimal("-5")) == Decimal("0.00")


def test_v5_rate_below_100_no_extras():
    # VR-3 + A-1: 0 < r < 100, neither shipping nor fee applied (V3/V5):
    # base = 100 -> 25.00
    assert _vat(vat_rate_percent=Decimal("25")) == Decimal("25.00")


def test_v5_rate_at_or_above_100():
    # VR-4: r >= 100 allowed (V5): base 100 @ 150 -> 150.00
    assert _vat(vat_rate_percent=Decimal("150")) == Decimal("150.00")


def test_v3_apply_shipping_only():
    # A-2: apply_to_shipping only -> base = 100 + 20 = 120 @ 25% -> 30.00
    assert _vat(apply_to_shipping=True, apply_to_fee=False) == Decimal("30.00")


def test_v3_apply_fee_only():
    # A-3: apply_to_fee only -> base = 100 + 10 = 110 @ 25% -> 27.50
    assert _vat(apply_to_shipping=False, apply_to_fee=True) == Decimal("27.50")


def test_v3_apply_both():
    # A-4: both applied -> base = 100 + 20 + 10 = 130 @ 25% -> 32.50
    assert _vat(apply_to_shipping=True, apply_to_fee=True) == Decimal("32.50")


def test_v4_base_nonpositive_zero():
    # M-9: base <= 0 (zero AND negative taxable) -> 0.00, even with a
    # positive rate (V4)
    assert _vat(taxable_subtotal=Decimal("-50")) == Decimal("0.00")
    assert _vat(taxable_subtotal=Decimal("0")) == Decimal("0.00")


def test_v3_negative_shipping_reduces_base():
    # M-10/M-11: a negative money input that IS applied reduces the VAT base
    # (V3 composition happens before the V4 clamp): base 30-10 = 20 @ 25% -> 5.00
    assert _vat(
        taxable_subtotal=Decimal("30.00"),
        shipping=Decimal("-10.00"),
        apply_to_shipping=True,
        apply_to_fee=False,
    ) == Decimal("5.00")
    assert _vat(
        taxable_subtotal=Decimal("30.00"),
        shipping=Decimal("0"),
        fee=Decimal("-10.00"),
        apply_to_shipping=False,
        apply_to_fee=True,
    ) == Decimal("5.00")


def test_v_rounding_propagates_down():
    # R-9: rounding reaches compute_vat (V5): 100.05*10/100 = 10.005 -> 10.00
    assert (
        _vat(
            taxable_subtotal=Decimal("100.05"),
            shipping=Decimal("0"),
            fee=Decimal("0"),
            vat_rate_percent=Decimal("10"),
            rounding="down",
        )
        == Decimal("10.00")
    )


# ---------------------------------------------------------------------------
# compute_totals — subtotal/discount/shipping classes, VAT resolution, record
# ---------------------------------------------------------------------------


def test_t1_negative_subtotal_reported_as_is():
    # M-14: negative subtotal reported as-is; taxable floored at 0.00;
    # total non-negative (T1/T3/T7)
    b = _totals(subtotal=Decimal("-50"))
    assert b.subtotal == Decimal("-50.00")
    assert b.taxable_subtotal == Decimal("0.00")
    assert b.total == Decimal("0.00")


def test_t1_zero_subtotal():
    # M-13: zero subtotal -> all-zero breakdown (T1/T3)
    b = _totals(subtotal=Decimal("0"))
    assert b.subtotal == Decimal("0.00")
    assert b.taxable_subtotal == Decimal("0.00")
    assert b.total == Decimal("0.00")


def test_t1_subcent_subtotal_quantized():
    # M-12: >2dp subtotal quantized to the cent (T1)
    b = _totals(subtotal=Decimal("100.009"))
    assert b.subtotal == Decimal("100.01")
    assert b.total == Decimal("100.01")


def test_t2_positive_discount_applied():
    # M-15: positive discount quantized and subtracted (T2/T3)
    b = _totals(subtotal=Decimal("100"), discount=Decimal("20"))
    assert b.discount == Decimal("20.00")
    assert b.taxable_subtotal == Decimal("80.00")
    assert b.total == Decimal("80.00")


def test_t2_subcent_discount_quantized():
    # M-16: positive >2dp discount quantized (half_up): 20.005 -> 20.01 (T2)
    b = _totals(subtotal=Decimal("100.00"), discount=Decimal("20.005"))
    assert b.discount == Decimal("20.01")
    assert b.taxable_subtotal == Decimal("79.99")


def test_t2_nonpositive_discount_ignored():
    # M-17: discount <= 0 is ONE class (T2): zero and negative both report
    # 0.00 and do not reduce the taxable subtotal
    b0 = _totals(subtotal=Decimal("100"), discount=Decimal("0"))
    bneg = _totals(subtotal=Decimal("100"), discount=Decimal("-10"))
    for b in (b0, bneg):
        assert b.discount == Decimal("0.00")
        assert b.taxable_subtotal == Decimal("100.00")
        assert b.total == Decimal("100.00")


def test_t3_discount_exceeding_subtotal_floors_taxable():
    # M-18: discount > subtotal floors taxable at 0.00; the excess is not
    # refunded anywhere else (T3)
    b = _totals(subtotal=Decimal("100"), discount=Decimal("150"), shipping=Decimal("10"))
    assert b.discount == Decimal("150.00")
    assert b.taxable_subtotal == Decimal("0.00")
    assert b.shipping == Decimal("10.00")
    assert b.total == Decimal("10.00")


def test_t4_positive_shipping_quantized():
    # M-19: positive >2dp shipping quantized and added (T4/T7)
    b = _totals(subtotal=Decimal("100"), shipping=Decimal("5.555"))
    assert b.shipping == Decimal("5.56")
    assert b.total == Decimal("105.56")


def test_t4_nonpositive_shipping_zero():
    # M-20: shipping <= 0 is ONE class (T4): zero and negative both report
    # 0.00 and are not added
    b0 = _totals(subtotal=Decimal("100"), shipping=Decimal("0"))
    bneg = _totals(subtotal=Decimal("100"), shipping=Decimal("-3"))
    for b in (b0, bneg):
        assert b.shipping == Decimal("0.00")
        assert b.total == Decimal("100.00")


def test_t5_fee_disabled_zero_in_totals():
    # E-3: fee_enabled=False -> fee 0.00 in the breakdown (F1 via T5)
    b = _totals(
        subtotal=Decimal("100"),
        fee_enabled=False,
        fee_type="percent",
        fee_value=Decimal("50"),
    )
    assert b.fee == Decimal("0.00")
    assert b.total == Decimal("100.00")


def test_t5_fee_computed_from_taxable_not_subtotal():
    # C-1: fee is derived from the TAXABLE subtotal, not the raw subtotal (T5):
    # taxable 50 -> percent 10 -> fee 5.00
    b = _totals(
        subtotal=Decimal("200"),
        discount=Decimal("150"),
        fee_enabled=True,
        fee_type="percent",
        fee_value=Decimal("10"),
    )
    assert b.taxable_subtotal == Decimal("50.00")
    assert b.fee == Decimal("5.00")
    assert b.total == Decimal("55.00")


def test_t6_vat_disabled_ignores_override():
    # E-4: vat_enabled=False -> vat 0.00 and a supplied override is
    # IGNORED (T6, first arm takes precedence)
    b = _totals(subtotal=Decimal("100"), vat_enabled=False, vat_override=Decimal("99.00"))
    assert b.vat == Decimal("0.00")
    assert b.total == Decimal("100.00")


def test_t6_positive_override_used_rate_ignored():
    # M-22: override present and positive -> VAT = round(override); the rate
    # and apply flags are ignored (even a rate of 0) (T6, second arm)
    b = _totals(
        subtotal=Decimal("100"),
        vat_enabled=True,
        vat_rate_percent=Decimal("0"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=False,
        vat_override=Decimal("12.345"),
    )
    assert b.vat == Decimal("12.35")
    assert b.total == Decimal("112.35")


def test_t6_nonpositive_override_clamped():
    # M-23: override <= 0 is ONE class (T6): zero and negative both clamp
    # to 0.00
    b0 = _totals(subtotal=Decimal("100"), vat_enabled=True, vat_override=Decimal("0"))
    bneg = _totals(subtotal=Decimal("100"), vat_enabled=True, vat_override=Decimal("-4"))
    for b in (b0, bneg):
        assert b.vat == Decimal("0.00")
        assert b.total == Decimal("100.00")


def test_t6_none_override_computed_with_apply_flags():
    # M-21/A-5: override None -> VAT computed from base = taxable + shipping
    # + fee when both vat_apply flags true (T6 third arm, V3/V5):
    # base = 100+20+10 = 130 @ 10% -> 13.00
    b = _totals(
        subtotal=Decimal("100"),
        shipping=Decimal("20"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("10"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
    )
    assert b.vat == Decimal("13.00")
    assert b.total == Decimal("143.00")


def test_t7_total_identity_full_scenario():
    # C-2/C-3: full composition — total = taxable + shipping + fee + vat (T7)
    # and all 8 fields reported (T8): taxable 150, fee 150*10% = 15.00,
    # vat (150+20+15)*10% = 18.50, total 203.50
    b = _totals(
        subtotal=Decimal("200"),
        discount=Decimal("50"),
        shipping=Decimal("20"),
        fee_enabled=True,
        fee_type="percent",
        fee_value=Decimal("10"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
    )
    assert isinstance(b, PricingBreakdown)
    assert b.subtotal == Decimal("200.00")
    assert b.discount == Decimal("50.00")
    assert b.taxable_subtotal == Decimal("150.00")
    assert b.shipping == Decimal("20.00")
    assert b.fee == Decimal("15.00")
    assert b.vat == Decimal("18.50")
    assert b.total == Decimal("203.50")


def test_t8_breakdown_frozen():
    # C-4: the record is immutable (T8)
    b = _totals(subtotal=Decimal("100"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.total = Decimal("0.00")


def test_t_rounding_propagates_in_totals():
    # R-10: the totals-level rounding class changes derived components:
    # flat fee 7.779 with "down" -> fee 7.77, total 107.77 (T5/T7)
    b = _totals(
        subtotal=Decimal("100"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("7.779"),
        rounding="down",
    )
    assert b.fee == Decimal("7.77")
    assert b.total == Decimal("107.77")
