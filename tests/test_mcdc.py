"""MC/DC (modified condition/decision coverage) suite for ``pricing``.

Derived from ``tss/lab/docs/mcdc.md`` (the derivation document) against
``tss/lab/SPEC.md`` §9 and ``tss/lab/pricing.py``. Line citations in the
docstrings refer to ``pricing.py``.

Each test executes BOTH rows of one minimal MC/DC pair: the target condition
flips, every other condition feeding the same decision (and every guard that
could mask the outcome) is held fixed, and the decision's observable outcome
is asserted to flip with exact ``Decimal`` values. The unreachable condition
C15 (``total < 0``, pricing.py:148, ``pragma: no cover``) has no pair — see
docs/mcdc.md §4.
"""

from decimal import Decimal

import pricing


def test_mcdc_c01_compute_fee_not_enabled():
    """P1 / C1 ``not enabled`` (pricing.py:55).

    Fixed: fee_type="flat", fee_value=3, taxable=100. Only ``enabled`` flips.
    """
    off = pricing.compute_fee(
        taxable_subtotal=Decimal("100"),
        enabled=False,
        fee_type="flat",
        fee_value=Decimal("3"),
    )
    on = pricing.compute_fee(
        taxable_subtotal=Decimal("100"),
        enabled=True,
        fee_type="flat",
        fee_value=Decimal("3"),
    )
    assert off == Decimal("0.00")  # C1 True  -> early return
    assert on == Decimal("3.00")  # C1 False -> fee charged


def test_mcdc_c02_compute_fee_value_le_zero():
    """P2 / C2 ``fee_value <= 0`` (pricing.py:57).

    Fixed: enabled=True (C1 False so it cannot mask), fee_type="flat",
    taxable=100. Only the sign of fee_value flips.
    """
    negative = pricing.compute_fee(
        taxable_subtotal=Decimal("100"),
        enabled=True,
        fee_type="flat",
        fee_value=Decimal("-3"),
    )
    positive = pricing.compute_fee(
        taxable_subtotal=Decimal("100"),
        enabled=True,
        fee_type="flat",
        fee_value=Decimal("3"),
    )
    assert negative == Decimal("0.00")  # C2 True  -> early return
    assert positive == Decimal("3.00")  # C2 False -> flat fee


def test_mcdc_c03_compute_fee_type_percent():
    """P3 / C3 ``fee_type == "percent"`` (pricing.py:59).

    Fixed: enabled=True, fee_value=5, taxable=200. Only fee_type flips.
    """
    flat = pricing.compute_fee(
        taxable_subtotal=Decimal("200"),
        enabled=True,
        fee_type="flat",
        fee_value=Decimal("5"),
    )
    percent = pricing.compute_fee(
        taxable_subtotal=Decimal("200"),
        enabled=True,
        fee_type="percent",
        fee_value=Decimal("5"),
    )
    assert flat == Decimal("5.00")  # C3 False -> flat arm
    assert percent == Decimal("10.00")  # C3 True  -> 200*5/100


def test_mcdc_c04_compute_vat_not_enabled():
    """P4 / C4 ``not enabled`` (pricing.py:77).

    Fixed: taxable=100, shipping=10, fee=5, rate=10, both apply flags True.
    Only ``enabled`` flips.
    """
    off = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("10"),
        fee=Decimal("5"),
        enabled=False,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=True,
        apply_to_fee=True,
    )
    on = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("10"),
        fee=Decimal("5"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=True,
        apply_to_fee=True,
    )
    assert off == Decimal("0.00")  # C4 True  -> early return
    assert on == Decimal("11.50")  # C4 False -> base 115 * 10/100


def test_mcdc_c05_compute_vat_rate_le_zero():
    """P5 / C5 ``vat_rate_percent <= 0`` (pricing.py:79).

    Fixed: enabled=True, taxable=100, shipping=0, fee=0, apply flags False.
    Only the sign of the rate flips.
    """
    negative = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("0"),
        fee=Decimal("0"),
        enabled=True,
        vat_rate_percent=Decimal("-10"),
        apply_to_shipping=False,
        apply_to_fee=False,
    )
    positive = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("0"),
        fee=Decimal("0"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=False,
        apply_to_fee=False,
    )
    assert negative == Decimal("0.00")  # C5 True  -> early return
    assert positive == Decimal("10.00")  # C5 False -> 100*10/100


def test_mcdc_c06_compute_vat_apply_shipping():
    """P6 / C6 ``apply_to_shipping`` (pricing.py:82).

    Fixed: enabled=True, rate=10, taxable=100, shipping=10, fee=0,
    apply_to_fee=False. Base stays > 0 both rows so C8 cannot mask.
    """
    without = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("10"),
        fee=Decimal("0"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=False,
        apply_to_fee=False,
    )
    with_ = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("10"),
        fee=Decimal("0"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=True,
        apply_to_fee=False,
    )
    assert without == Decimal("10.00")  # C6 False -> base 100
    assert with_ == Decimal("11.00")  # C6 True  -> base 110


def test_mcdc_c07_compute_vat_apply_fee():
    """P7 / C7 ``apply_to_fee`` (pricing.py:84).

    Fixed: enabled=True, rate=10, taxable=100, shipping=0, fee=8,
    apply_to_shipping=False.
    """
    without = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("0"),
        fee=Decimal("8"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=False,
        apply_to_fee=False,
    )
    with_ = pricing.compute_vat(
        taxable_subtotal=Decimal("100"),
        shipping=Decimal("0"),
        fee=Decimal("8"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=False,
        apply_to_fee=True,
    )
    assert without == Decimal("10.00")  # C7 False -> base 100
    assert with_ == Decimal("10.80")  # C7 True  -> base 108


def test_mcdc_c08_compute_vat_base_le_zero():
    """P8 / C8 ``base <= 0`` (pricing.py:86).

    Fixed: enabled=True, rate=10, apply flags False, shipping=0, fee=0.
    The decision's sole operand ``base`` flips sign via taxable_subtotal
    (interior values; the base=0 boundary belongs to the BVA suite).
    """
    negative_base = pricing.compute_vat(
        taxable_subtotal=Decimal("-40"),
        shipping=Decimal("0"),
        fee=Decimal("0"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=False,
        apply_to_fee=False,
    )
    positive_base = pricing.compute_vat(
        taxable_subtotal=Decimal("40"),
        shipping=Decimal("0"),
        fee=Decimal("0"),
        enabled=True,
        vat_rate_percent=Decimal("10"),
        apply_to_shipping=False,
        apply_to_fee=False,
    )
    assert negative_base == Decimal("0.00")  # C8 True  -> early return
    assert positive_base == Decimal("4.00")  # C8 False -> 40*10/100


def _totals(discount, **overrides):
    """Common fixed context for the compute_totals pairs (P9-P14)."""
    kwargs = dict(
        subtotal=Decimal("100"),
        discount=discount,
        shipping=Decimal("0"),
        fee_enabled=False,
        fee_type="flat",
        fee_value=Decimal("0"),
        vat_enabled=False,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=False,
    )
    kwargs.update(overrides)
    return pricing.compute_totals(**kwargs)


def test_mcdc_c09_totals_discount_positive():
    """P9 / C9 ``discount > 0`` (pricing.py:108).

    Fixed: subtotal=100, shipping=0, fee/VAT disabled. Only the sign of
    discount flips; the reported discount field is the ternary's outcome.
    """
    negative = _totals(Decimal("-2"))
    positive = _totals(Decimal("5"))
    assert negative.discount == Decimal("0.00")  # C9 False -> 0.00 branch
    assert negative.taxable_subtotal == Decimal("100.00")
    assert negative.total == Decimal("100.00")
    assert positive.discount == Decimal("5.00")  # C9 True -> quantized
    assert positive.taxable_subtotal == Decimal("95.00")
    assert positive.total == Decimal("95.00")


def test_mcdc_c10_totals_taxable_negative():
    """P10 / C10 ``taxable < 0`` (pricing.py:111).

    Fixed: subtotal=100, shipping=0, fee/VAT disabled, discount>0 True in
    both rows (C9 fixed) — only the raw taxable crosses zero.
    """
    oversized = _totals(Decimal("120"))
    normal = _totals(Decimal("80"))
    assert oversized.taxable_subtotal == Decimal("0.00")  # C10 True -> floor
    assert oversized.total == Decimal("0.00")
    assert normal.taxable_subtotal == Decimal("20.00")  # C10 False -> keep
    assert normal.total == Decimal("20.00")


def test_mcdc_c11_totals_shipping_positive():
    """P11 / C11 ``shipping > 0`` (pricing.py:115).

    Fixed: subtotal=100, discount=0, fee/VAT disabled. Only the sign of
    shipping flips; the reported shipping field is the ternary's outcome.
    """
    negative = _totals(Decimal("0"), shipping=Decimal("-3"))
    positive = _totals(Decimal("0"), shipping=Decimal("7"))
    assert negative.shipping == Decimal("0.00")  # C11 False -> 0.00 branch
    assert negative.total == Decimal("100.00")
    assert positive.shipping == Decimal("7.00")  # C11 True -> quantized
    assert positive.total == Decimal("107.00")


def test_mcdc_c12_totals_vat_not_enabled():
    """P12 / C12 ``not vat_enabled`` (pricing.py:124) — arm 1 vs arm 3.

    Fixed: vat_override=None in both rows (C13 False), taxable=100, rate=10,
    apply flags False. Only vat_enabled flips.
    """
    disabled = _totals(Decimal("0"))
    enabled = _totals(Decimal("0"), vat_enabled=True)
    assert disabled.vat == Decimal("0.00")  # C12 True  -> arm 1
    assert disabled.total == Decimal("100.00")
    assert enabled.vat == Decimal("10.00")  # C12 False -> arm 3 (computed)
    assert enabled.total == Decimal("110.00")


def test_mcdc_c13_totals_override_not_none():
    """P13 / C13 ``vat_override is not None`` (pricing.py:126) — arm 3 vs arm 2.

    Fixed: vat_enabled=True in both rows (C12 False, so C13 is not masked),
    taxable=100, rate=10, apply flags False. Only override presence flips.
    """
    computed = _totals(Decimal("0"), vat_enabled=True, vat_override=None)
    overridden = _totals(
        Decimal("0"), vat_enabled=True, vat_override=Decimal("3")
    )
    assert computed.vat == Decimal("10.00")  # C13 False -> arm 3 (computed)
    assert computed.total == Decimal("110.00")
    assert overridden.vat == Decimal("3.00")  # C13 True -> arm 2 (override)
    assert overridden.total == Decimal("103.00")


def test_mcdc_c14_totals_override_positive():
    """P14 / C14 ``vat_override > 0`` clamp ternary (pricing.py:128).

    Fixed: vat_enabled=True and override present in both rows (C12 False,
    C13 True). Only the sign of the override flips.
    """
    clamped = _totals(Decimal("0"), vat_enabled=True, vat_override=Decimal("-4"))
    honored = _totals(Decimal("0"), vat_enabled=True, vat_override=Decimal("4"))
    assert clamped.vat == Decimal("0.00")  # C14 False -> clamped to 0.00
    assert clamped.total == Decimal("100.00")
    assert honored.vat == Decimal("4.00")  # C14 True -> override used
    assert honored.total == Decimal("104.00")
