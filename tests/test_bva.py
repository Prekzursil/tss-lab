"""BVA (boundary value analysis) suite — derived from SPEC.md §9 (BVA anchor).

Scope: boundary-value neighbors ONLY (clamps at 0, cent ties per rounding mode,
quantization at 0.01, sign boundaries, VAT override switch points).
Derivation tables: tss/lab/docs/bva.md.  All assertions are exact Decimal
equality; two-decimal shape (R1) is asserted via the decimal exponent.
Tests are independent: no shared fixtures, no ordering dependence.

B-id references below map to the tables in docs/bva.md.
"""

from decimal import Decimal

import pytest

from pricing import compute_fee, compute_totals, compute_vat, quantize_money

D = Decimal

MODES = ("half_up", "half_even", "up", "down")


def totals(**overrides):
    """compute_totals with a neutral baseline; each call is self-contained."""
    kwargs = dict(
        subtotal=D("0"),
        discount=D("0"),
        shipping=D("0"),
        fee_enabled=False,
        fee_type="flat",
        fee_value=D("0"),
        vat_enabled=False,
        vat_rate_percent=D("0"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=False,
    )
    kwargs.update(overrides)
    return compute_totals(**kwargs)


# --------------------------------------------------------------------------
# B1-B6: quantize_money boundaries (R1-R4)
# --------------------------------------------------------------------------

# B1: 5-point neighbor set around the +2.345 cent tie, per mode.
B1_TIE_POSITIVE = [
    # value, expected per mode (half_up, half_even, up, down)
    ("2.344", "2.34", "2.34", "2.35", "2.34"),
    ("2.3449", "2.34", "2.34", "2.35", "2.34"),
    ("2.345", "2.35", "2.34", "2.35", "2.34"),
    ("2.3451", "2.35", "2.35", "2.35", "2.34"),
    ("2.346", "2.35", "2.35", "2.35", "2.34"),
]


@pytest.mark.parametrize(
    "value,half_up,half_even,up,down", B1_TIE_POSITIVE, ids=[r[0] for r in B1_TIE_POSITIVE]
)
def test_b1_quantize_tie_boundary_positive(value, half_up, half_even, up, down):
    expected = {"half_up": half_up, "half_even": half_even, "up": up, "down": down}
    for mode in MODES:
        got = quantize_money(D(value), rounding=mode)
        assert got == D(expected[mode]), (mode, value, got)
        assert got.as_tuple().exponent == -2, (mode, value, got)


# B2: negative mirror of the tie (away-from-zero vs toward-zero symmetry, R2).
B2_TIE_NEGATIVE = [
    ("-2.344", "-2.34", "-2.34", "-2.35", "-2.34"),
    ("-2.345", "-2.35", "-2.34", "-2.35", "-2.34"),
    ("-2.346", "-2.35", "-2.35", "-2.35", "-2.34"),
]


@pytest.mark.parametrize(
    "value,half_up,half_even,up,down", B2_TIE_NEGATIVE, ids=[r[0] for r in B2_TIE_NEGATIVE]
)
def test_b2_quantize_tie_boundary_negative(value, half_up, half_even, up, down):
    expected = {"half_up": half_up, "half_even": half_even, "up": up, "down": down}
    for mode in MODES:
        assert quantize_money(D(value), rounding=mode) == D(expected[mode]), (mode, value)


# B3: half_even picks the even cent on both sides of zero.
@pytest.mark.parametrize(
    "value,expected",
    [
        ("2.345", "2.34"),  # 4 is even
        ("2.355", "2.36"),  # 6 is even
        ("-2.345", "-2.34"),
        ("-2.355", "-2.36"),
    ],
)
def test_b3_half_even_even_tie_pair(value, expected):
    assert quantize_money(D(value), rounding="half_even") == D(expected)


# B4: smallest surviving cent — neighbors around the 0.01 quantum.
B4_MIN_CENT = [
    # value, half_up, half_even, up, down
    ("0.004", "0.00", "0.00", "0.01", "0.00"),
    ("0.005", "0.01", "0.00", "0.01", "0.00"),
    ("0.006", "0.01", "0.01", "0.01", "0.00"),
]


@pytest.mark.parametrize(
    "value,half_up,half_even,up,down", B4_MIN_CENT, ids=[r[0] for r in B4_MIN_CENT]
)
def test_b4_smallest_surviving_cent(value, half_up, half_even, up, down):
    expected = {"half_up": half_up, "half_even": half_even, "up": up, "down": down}
    for mode in MODES:
        got = quantize_money(D(value), rounding=mode)
        assert got == D(expected[mode]), (mode, value, got)
        assert got.as_tuple().exponent == -2, (mode, value, got)


# B5: exactly-2dp shape (R1) and idempotency at 2dp (R4) for every mode.
@pytest.mark.parametrize("value", ["0", "2", "2.35", "-2.35", "123.45", "-123.45"])
@pytest.mark.parametrize("mode", MODES)
def test_b5_two_dp_shape_and_idempotency(value, mode):
    got = quantize_money(D(value), rounding=mode)
    assert got == D(value)  # already-2dp inputs (0 and 2 gain .00, equal values)
    assert got.as_tuple().exponent == -2, (mode, value, got)
    assert quantize_money(got, rounding=mode) == got  # R4


# B6: unrecognized rounding mode behaves exactly as half_up — probed AT the
# tie (2.345) and below it (2.344), where mode behavior is distinguishable.
@pytest.mark.parametrize("bogus_mode", ["bogus", "", "HALF_UP", "round"], ids=repr)
def test_b6_unrecognized_mode_falls_back_to_half_up_at_tie(bogus_mode):
    assert quantize_money(D("2.345"), rounding=bogus_mode) == D("2.35")
    assert quantize_money(D("2.344"), rounding=bogus_mode) == D("2.34")


# --------------------------------------------------------------------------
# B7-B10: compute_fee boundaries (F2-F5)
# --------------------------------------------------------------------------

# B7: fee_value = 0 clamp, flat fee (below / at / above).
B7_FEE_ZERO_FLAT = [
    ("-0.01", "0.00"),
    ("-0.001", "0.00"),
    ("0", "0.00"),
    ("0.00", "0.00"),
    ("0.001", "0.00"),  # above zero but quantizes to 0.00 (B4 interaction)
    ("0.004", "0.00"),
    ("0.005", "0.01"),  # minimum surviving positive fee, half_up
]


@pytest.mark.parametrize(
    "fee_value,expected", B7_FEE_ZERO_FLAT, ids=[r[0] for r in B7_FEE_ZERO_FLAT]
)
def test_b7_fee_value_zero_boundary_flat(fee_value, expected):
    assert (
        compute_fee(
            taxable_subtotal=D("100"),
            enabled=True,
            fee_type="flat",
            fee_value=D(fee_value),
        )
        == D(expected)
    )


def test_b7_fee_value_tie_min_surviving_down_mode():
    # Under "down", even the 0.005 flat fee quantizes back to 0.00.
    assert (
        compute_fee(
            taxable_subtotal=D("100"),
            enabled=True,
            fee_type="flat",
            fee_value=D("0.005"),
            rounding="down",
        )
        == D("0.00")
    )


# B8: fee_value = 0 clamp, percent fee.
B8_FEE_ZERO_PERCENT = [
    ("-1", "0.00"),
    ("-0.001", "0.00"),
    ("0", "0.00"),
    ("0.001", "0.00"),  # 100 * 0.001 / 100 = 0.001 -> 0.00
    ("0.005", "0.01"),  # 100 * 0.005 / 100 = 0.005 tie -> away from zero
]


@pytest.mark.parametrize(
    "fee_value,expected", B8_FEE_ZERO_PERCENT, ids=[r[0] for r in B8_FEE_ZERO_PERCENT]
)
def test_b8_fee_value_zero_boundary_percent(fee_value, expected):
    assert (
        compute_fee(
            taxable_subtotal=D("100"),
            enabled=True,
            fee_type="percent",
            fee_value=D(fee_value),
        )
        == D(expected)
    )


# B9: flat fee sub-cent tie — fee = round(fee_value) directly (F4).
@pytest.mark.parametrize(
    "mode,expected",
    [("half_up", "2.35"), ("half_even", "2.34"), ("up", "2.35"), ("down", "2.34")],
)
def test_b9_flat_fee_tie_per_mode(mode, expected):
    assert (
        compute_fee(
            taxable_subtotal=D("100"),
            enabled=True,
            fee_type="flat",
            fee_value=D("2.345"),
            rounding=mode,
        )
        == D(expected)
    )


def test_b9_flat_fee_tie_neighbors_half_up():
    kwargs = dict(taxable_subtotal=D("100"), enabled=True, fee_type="flat")
    assert compute_fee(fee_value=D("2.344"), **kwargs) == D("2.34")
    assert compute_fee(fee_value=D("2.346"), **kwargs) == D("2.35")


# B10a: percent fee tie — raw product lands exactly on the cent tie.
@pytest.mark.parametrize(
    "mode,expected",
    [("half_up", "2.35"), ("half_even", "2.34"), ("up", "2.35"), ("down", "2.34")],
)
def test_b10_percent_fee_tie_per_mode(mode, expected):
    assert (
        compute_fee(
            taxable_subtotal=D("23.45"),
            enabled=True,
            fee_type="percent",
            fee_value=D("10"),
            rounding=mode,
        )
        == D(expected)
    )


def test_b10_percent_fee_tie_neighbors_half_up():
    kwargs = dict(enabled=True, fee_type="percent", fee_value=D("10"))
    assert compute_fee(taxable_subtotal=D("23.44"), **kwargs) == D("2.34")
    assert compute_fee(taxable_subtotal=D("23.46"), **kwargs) == D("2.35")


# B10b: taxable sign boundary — spec F5 only guarantees >= 0 for
# non-negative subtotals; below zero the F3 formula applies literally.
B10_TAXABLE_SIGN = [
    ("-100", "-10.00"),
    ("-0.001", "0.00"),  # -0.0001 quantizes to -0.00 == 0.00
    ("0", "0.00"),
    ("0.001", "0.00"),  # 0.0001 -> 0.00
    ("100", "10.00"),
]


@pytest.mark.parametrize(
    "taxable,expected", B10_TAXABLE_SIGN, ids=[r[0] for r in B10_TAXABLE_SIGN]
)
def test_b10_fee_taxable_sign_boundary(taxable, expected):
    assert (
        compute_fee(
            taxable_subtotal=D(taxable),
            enabled=True,
            fee_type="percent",
            fee_value=D("10"),
        )
        == D(expected)
    )


# --------------------------------------------------------------------------
# B11-B13: compute_vat boundaries (V2, V4, V5)
# --------------------------------------------------------------------------

# B11: vat_rate_percent = 0 clamp at fixed base 100.
B11_RATE_ZERO = [
    ("-1", "0.00"),
    ("-0.001", "0.00"),
    ("0", "0.00"),
    ("0.00", "0.00"),
    ("0.001", "0.00"),  # 100 * 0.001 / 100 = 0.001 -> 0.00
    ("0.004", "0.00"),
    ("0.005", "0.01"),  # minimum rate yielding nonzero VAT at base 100
]


@pytest.mark.parametrize("rate,expected", B11_RATE_ZERO, ids=[r[0] for r in B11_RATE_ZERO])
def test_b11_vat_rate_zero_boundary(rate, expected):
    assert (
        compute_vat(
            taxable_subtotal=D("100"),
            shipping=D("0"),
            fee=D("0"),
            enabled=True,
            vat_rate_percent=D(rate),
            apply_to_shipping=False,
            apply_to_fee=False,
        )
        == D(expected)
    )


def test_b11_vat_rate_min_surviving_down_mode():
    assert (
        compute_vat(
            taxable_subtotal=D("100"),
            shipping=D("0"),
            fee=D("0"),
            enabled=True,
            vat_rate_percent=D("0.005"),
            apply_to_shipping=False,
            apply_to_fee=False,
            rounding="down",
        )
        == D("0.00")
    )


# B12: composed base = 0 clamp (V4) — base crossed via shipping offset.
B12_BASE_ZERO = [
    ("-100.01", "-0.01", "0.00"),
    ("-100.001", "-0.001", "0.00"),
    ("-100.00", "0", "0.00"),
    ("-99.999", "0.001", "0.00"),  # 0.001 * 100/100 = 0.001 -> 0.00
    ("-99.99", "0.01", "0.01"),  # smallest surviving positive base
]


@pytest.mark.parametrize(
    "shipping,base,vat_expected",
    B12_BASE_ZERO,
    ids=[f"base={b}" for _, b, _ in B12_BASE_ZERO],
)
def test_b12_vat_composed_base_zero_boundary(shipping, base, vat_expected):
    assert (
        compute_vat(
            taxable_subtotal=D("100"),
            shipping=D(shipping),
            fee=D("0"),
            enabled=True,
            vat_rate_percent=D("100"),
            apply_to_shipping=True,
            apply_to_fee=False,
        )
        == D(vat_expected)
    )


@pytest.mark.parametrize(
    "taxable,expected", [("-0.01", "0.00"), ("0", "0.00"), ("0.01", "0.01")]
)
def test_b12_vat_direct_base_zero_boundary(taxable, expected):
    assert (
        compute_vat(
            taxable_subtotal=D(taxable),
            shipping=D("0"),
            fee=D("0"),
            enabled=True,
            vat_rate_percent=D("100"),
            apply_to_shipping=False,
            apply_to_fee=False,
        )
        == D(expected)
    )


# B13: VAT rate tie at the third decimal (V5): raw = taxable * 10 / 100.
B13_VAT_TIE = [
    # taxable, expected per mode
    ("23.44", "2.34", "2.34", "2.35", "2.34"),
    ("23.45", "2.35", "2.34", "2.35", "2.34"),
    ("23.46", "2.35", "2.35", "2.35", "2.34"),
]


@pytest.mark.parametrize(
    "taxable,half_up,half_even,up,down", B13_VAT_TIE, ids=[r[0] for r in B13_VAT_TIE]
)
def test_b13_vat_tie_boundary_per_mode(taxable, half_up, half_even, up, down):
    expected = {"half_up": half_up, "half_even": half_even, "up": up, "down": down}
    for mode in MODES:
        got = compute_vat(
            taxable_subtotal=D(taxable),
            shipping=D("0"),
            fee=D("0"),
            enabled=True,
            vat_rate_percent=D("10"),
            apply_to_shipping=False,
            apply_to_fee=False,
            rounding=mode,
        )
        assert got == D(expected[mode]), (mode, taxable, got)


# --------------------------------------------------------------------------
# B14-B20: compute_totals boundaries (T2-T7)
# --------------------------------------------------------------------------

# B14: discount = 0 clamp (T2) — below / at / above, incl. min surviving.
B14_DISCOUNT_ZERO = [
    ("-0.01", "0.00", "100.00", "100.00"),
    ("-0.001", "0.00", "100.00", "100.00"),
    ("0", "0.00", "100.00", "100.00"),
    ("0.001", "0.00", "100.00", "100.00"),
    ("0.004", "0.00", "100.00", "100.00"),
    ("0.005", "0.01", "99.99", "99.99"),
]


@pytest.mark.parametrize(
    "discount,discount_exp,taxable_exp,total_exp",
    B14_DISCOUNT_ZERO,
    ids=[f"d={d}" for d, _, _, _ in B14_DISCOUNT_ZERO],
)
def test_b14_totals_discount_zero_boundary(discount, discount_exp, taxable_exp, total_exp):
    b = totals(subtotal=D("100"), discount=D(discount))
    assert b.discount == D(discount_exp)
    assert b.taxable_subtotal == D(taxable_exp)
    assert b.total == D(total_exp)


def test_b14_totals_discount_min_surviving_down_mode():
    b = totals(subtotal=D("100"), discount=D("0.005"), rounding="down")
    assert b.discount == D("0.00")
    assert b.taxable_subtotal == D("100.00")
    assert b.total == D("100.00")


# B15: taxable = 0 floor at discount = subtotal (T3).
B15_TAXABLE_FLOOR = [
    ("99.99", "99.99", "0.01", "0.01"),
    ("100.00", "100.00", "0.00", "0.00"),
    ("100.01", "100.01", "0.00", "0.00"),  # excess discount not refunded
]


@pytest.mark.parametrize(
    "discount,discount_exp,taxable_exp,total_exp",
    B15_TAXABLE_FLOOR,
    ids=[f"d={d}" for d, _, _, _ in B15_TAXABLE_FLOOR],
)
def test_b15_totals_taxable_floor_boundary(discount, discount_exp, taxable_exp, total_exp):
    b = totals(subtotal=D("100"), discount=D(discount))
    assert b.discount == D(discount_exp)
    assert b.taxable_subtotal == D(taxable_exp)
    assert b.total == D(total_exp)


# B16: shipping = 0 clamp (T4).
B16_SHIPPING_ZERO = [
    ("-0.01", "0.00", "100.00"),
    ("-0.001", "0.00", "100.00"),
    ("0", "0.00", "100.00"),
    ("0.001", "0.00", "100.00"),
    ("0.005", "0.01", "100.01"),
]


@pytest.mark.parametrize(
    "shipping,shipping_exp,total_exp",
    B16_SHIPPING_ZERO,
    ids=[f"s={s}" for s, _, _ in B16_SHIPPING_ZERO],
)
def test_b16_totals_shipping_zero_boundary(shipping, shipping_exp, total_exp):
    b = totals(subtotal=D("100"), shipping=D(shipping))
    assert b.shipping == D(shipping_exp)
    assert b.total == D(total_exp)


def test_b16_totals_shipping_min_surviving_down_mode():
    b = totals(subtotal=D("100"), shipping=D("0.005"), rounding="down")
    assert b.shipping == D("0.00")
    assert b.total == D("100.00")


# B17: subtotal sign boundary — negative / zero / positive (T1, T3, T7).
B17_SUBTOTAL_SIGN = [
    ("-10.00", "-10.00", "0.00", "0.00"),
    ("-0.01", "-0.01", "0.00", "0.00"),
    ("0", "0.00", "0.00", "0.00"),
    ("0.01", "0.01", "0.01", "0.01"),
]


@pytest.mark.parametrize(
    "subtotal,subtotal_exp,taxable_exp,total_exp",
    B17_SUBTOTAL_SIGN,
    ids=[f"st={s}" for s, _, _, _ in B17_SUBTOTAL_SIGN],
)
def test_b17_totals_subtotal_sign_boundary(subtotal, subtotal_exp, taxable_exp, total_exp):
    b = totals(subtotal=D(subtotal))
    assert b.subtotal == D(subtotal_exp)
    assert b.subtotal.as_tuple().exponent == -2
    assert b.taxable_subtotal == D(taxable_exp)
    assert b.total == D(total_exp)
    assert b.total >= D("0.00")  # T7: non-negative total by construction


# B18: vat_override = 0 clamp and sub-cent quantization (T6).
# Computed VAT would be 10.00 (rate 10 on taxable 100) — the override arm
# must suppress computation for every row here.
B18_OVERRIDE_ZERO = [
    ("-0.01", "0.00"),
    ("-0.001", "0.00"),
    ("0", "0.00"),
    ("0.00", "0.00"),
    ("0.001", "0.00"),
    ("0.004", "0.00"),
    ("0.005", "0.01"),
]


@pytest.mark.parametrize(
    "override,vat_exp", B18_OVERRIDE_ZERO, ids=[f"ov={o}" for o, _ in B18_OVERRIDE_ZERO]
)
def test_b18_totals_vat_override_zero_boundary(override, vat_exp):
    b = totals(
        subtotal=D("100"),
        vat_enabled=True,
        vat_rate_percent=D("10"),
        vat_override=D(override),
    )
    assert b.vat == D(vat_exp)
    assert b.total == D("100") + D(vat_exp)


def test_b18_totals_vat_override_min_surviving_down_mode():
    b = totals(
        subtotal=D("100"),
        vat_enabled=True,
        vat_rate_percent=D("10"),
        vat_override=D("0.005"),
        rounding="down",
    )
    assert b.vat == D("0.00")
    assert b.total == D("100.00")


@pytest.mark.parametrize(
    "mode,expected",
    [("half_up", "2.35"), ("half_even", "2.34"), ("up", "2.35"), ("down", "2.34")],
)
def test_b18_totals_vat_override_tie_per_mode(mode, expected):
    b = totals(
        subtotal=D("100"),
        vat_enabled=True,
        vat_rate_percent=D("10"),
        vat_override=D("2.345"),
        rounding=mode,
    )
    assert b.vat == D(expected)
    assert b.total == D("100") + D(expected)


# B19: override-vs-computed switch points (T6) — value boundaries of the
# three-way switch: presence of the override vs its value vs the enabled gate.
B19_SWITCH = [
    # vat_enabled, override, vat_exp, total_exp
    (True, None, "10.00", "110.00"),  # computed
    (True, "0.00", "0.00", "100.00"),  # zero override suppresses computation
    (True, "5.00", "5.00", "105.00"),  # rate ignored under override
    (False, "5.00", "0.00", "100.00"),  # enabled gate wins over override
    (False, None, "0.00", "100.00"),
]


@pytest.mark.parametrize(
    "vat_enabled,override,vat_exp,total_exp",
    B19_SWITCH,
    ids=[f"en={e},ov={o}" for e, o, _, _ in B19_SWITCH],
)
def test_b19_totals_vat_override_switch_points(vat_enabled, override, vat_exp, total_exp):
    b = totals(
        subtotal=D("100"),
        vat_enabled=vat_enabled,
        vat_rate_percent=D("10"),
        vat_override=None if override is None else D(override),
    )
    assert b.vat == D(vat_exp)
    assert b.total == D(total_exp)


def test_b20_totals_minimal_sum_boundary():
    """T7 at the minimum surviving cent: every summand = 0.01 -> total 0.04."""
    b = totals(
        subtotal=D("0.01"),
        shipping=D("0.01"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=D("0.01"),
        vat_enabled=True,
        vat_rate_percent=D("0"),
        vat_override=D("0.01"),
    )
    assert b.taxable_subtotal == D("0.01")
    assert b.shipping == D("0.01")
    assert b.fee == D("0.01")
    assert b.vat == D("0.01")
    assert b.total == D("0.04")
    for field in (
        "subtotal",
        "discount",
        "taxable_subtotal",
        "shipping",
        "fee",
        "vat",
        "total",
    ):
        value = getattr(b, field)
        assert value.as_tuple().exponent == -2, (field, value)


def test_b20_totals_all_zero_boundary():
    """T7 at the all-zero boundary: every field exactly 0.00 (2 dp)."""
    b = totals()
    assert b.subtotal == D("0.00")
    assert b.discount == D("0.00")
    assert b.taxable_subtotal == D("0.00")
    assert b.shipping == D("0.00")
    assert b.fee == D("0.00")
    assert b.vat == D("0.00")
    assert b.total == D("0.00")
    assert b.total.as_tuple().exponent == -2
